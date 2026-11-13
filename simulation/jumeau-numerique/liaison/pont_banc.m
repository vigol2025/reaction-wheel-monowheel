function varargout = pont_banc(action, varargin)
% PONT_BANC  Liaison entre Simulink et le procédé piloté à distance.
%
% Aujourd'hui, le procédé au bout de la liaison est le jumeau Webots (contrôleur pont_simulink).
% Demain, ce sera l'ESP32 du banc réel : mêmes trames, même fonction.
%
%   pont_banc('ouvrir', config)   envoie les réglages (51 nombres) au jumeau, qui se remet en position de départ,
%                                 puis ouvre la liaison de télémétrie et la liaison de commande
%   trame = pont_banc('lire')     attend la trame de télémétrie (151 octets, colonne uint8)
%   pont_banc('ecrire', trame)    envoie la trame de commande (13 octets pour l'ESP32, 21 pour le jumeau Webots :
%                                 la poussée d'essai est ajoutée avant la somme de contrôle)
%   pont_banc('fermer')           ferme les liaisons : le jumeau attend le prochain lancement
%
% Appelée par le modèle jumeau_banc_rw : rappels StartFcn et StopFcn, blocs du sous-système « Jumeau Webots ».
%
% Pourquoi des connexions Java et pas tcpclient : la lecture de tcpclient (et des blocs TCP/IP de Simulink) attend
% 15,6 ms à chaque trame, ce qui limite la simulation à 0,6 fois le temps réel. La lecture directe répond en moins
% de 1 ms.

persistent telemetrie commande entree sortie tampon
HOTE = '127.0.0.1';
PORT_TELEMETRIE = 5005; PORT_COMMANDE = 5006; PORT_CONFIG = 5007;
N_TELEMETRIE = 151;                 % octets
DELAI_CONNEXION = 5000;             % ms
DELAI_LECTURE = 20000;              % ms sans trame : la simulation s'arrête avec une erreur

switch action
    case 'ouvrir'
        pont_banc('fermer');
        config = single(varargin{1});
        try
            c = connecter(HOTE, PORT_CONFIG, DELAI_CONNEXION, 30000);
        catch
            error('pont_banc:absent', ['Jumeau Webots : Webots ne répond pas. Ouvrir webots/worlds/banc_stabilisation.wbt ' ...
                'dans Webots, attendre le message « jumeau Webots prêt », puis relancer la simulation.']);
        end
        flux = c.getOutputStream();
        flux.write(typecast(config(:), 'int8'));
        flux.flush();
        accord = c.getInputStream().read();          % 1 : réglages acceptés ; 0 : refusés ; -1 : liaison coupée
        c.close();
        if accord ~= 1
            error('pont_banc:refus', 'Jumeau Webots : réglages refusés (voir la console de Webots).');
        end
        telemetrie = connecter(HOTE, PORT_TELEMETRIE, DELAI_CONNEXION, DELAI_LECTURE);
        commande = connecter(HOTE, PORT_COMMANDE, DELAI_CONNEXION, DELAI_LECTURE);
        entree = java.nio.channels.Channels.newChannel(telemetrie.getInputStream());
        sortie = commande.getOutputStream();
        tampon = java.nio.ByteBuffer.allocate(N_TELEMETRIE);

    case 'lire'
        if isempty(entree)
            error('pont_banc:ferme', 'Jumeau Webots : liaison fermée.');
        end
        tampon.clear();
        while tampon.hasRemaining()
            if entree.read(tampon) < 0
                error('pont_banc:coupure', 'Jumeau Webots : liaison coupée par Webots.');
            end
        end
        varargout{1} = typecast(tampon.array(), 'uint8');

    case 'ecrire'
        if isempty(sortie)
            error('pont_banc:ferme', 'Jumeau Webots : liaison fermée.');
        end
        sortie.write(typecast(uint8(varargin{1}(:)), 'int8'));
        sortie.flush();

    case 'fermer'
        if ~isempty(telemetrie), try, telemetrie.close(); catch, end, end
        if ~isempty(commande), try, commande.close(); catch, end, end
        telemetrie = []; commande = []; entree = []; sortie = []; tampon = [];

    otherwise
        error('pont_banc:action', 'Action inconnue : %s', action);
end
end

function s = connecter(hote, port, delai_connexion, delai_lecture)
s = java.net.Socket();
s.connect(java.net.InetSocketAddress(hote, port), delai_connexion);
s.setTcpNoDelay(true);
s.setSoTimeout(delai_lecture);
end

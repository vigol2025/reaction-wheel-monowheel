function varargout = pilotage_banc(action, varargin)
% PILOTAGE_BANC  Échange entre l'interface de pilotage (pilote_banc.m) et le modèle jumeau_banc_rw.
%
% Côté interface :
%   pilotage_banc('manche', roulis_deg, tangage_deg)   angles demandés par le manche
%   pilotage_banc('actif', vrai_ou_faux)               vrai : la référence suit le manche ; faux : la référence programmée
%   pilotage_banc('pousser', couple_Nm, duree_s)       poussée sur [roulis ; tangage] (N.m), dès le prochain pas de calcul
%   pilotage_banc('abonner', fonction)                 fonction(d) appelée à chaque envoi du tableau de bord, et avec []
%                                                      à la fin de la simulation ([] : plus d'abonné)
%   pilotage_banc('rythme', vrai_ou_faux)              vrai : la simulation est calée sur l'horloge par 'lire' (temps réel)
% Côté modèle (blocs MATLAB Function en appel extrinsèque, rappels StartFcn et StopFcn) :
%   s = pilotage_banc('lire', t)          s = [manche actif ; roulis (°) ; tangage (°) ; poussée roulis ; poussée tangage (N.m)]
%   pilotage_banc('afficher', t, v)       état du banc envoyé par le bloc « Tableau de bord » (voir « donnees » plus bas)
%   pilotage_banc('depart')               début d'une simulation
%   pilotage_banc('fin')                  fin d'une simulation
% Pour les essais automatiques :
%   pilotage_banc('scenario', S)          S : une ligne par instant, [t actif roulis tangage poussée_roulis poussée_tangage durée] ;
%                                         joué à la place de l'interface ([] : retour à l'interface)
%   pilotage_banc('raz')                  remet l'échange à zéro (l'abonné est gardé)
%   e = pilotage_banc('etat')             contenu de l'échange

persistent e
if isempty(e), e = initial(); end

switch action
    case 'manche'
        e.cible = [varargin{1}; varargin{2}];

    case 'actif'
        e.actif = logical(varargin{1});

    case 'pousser'
        e.demande = e.demande + 1;
        e.couple_demande = varargin{1}(:);
        e.duree_demande = varargin{2};

    case 'abonner'
        e.abonne = varargin{1};

    case 'scenario'
        e.scenario = varargin{1};

    case 'rythme'
        e.rythme = logical(varargin{1});

    case 'raz'
        ab = e.abonne;
        e = initial();
        e.abonne = ab;

    case 'etat'
        varargout{1} = e;

    case 'depart'
        e.t_dernier = inf;
        e.en_cours = true;

    case 'fin'
        e.en_cours = false;
        f = e.abonne;
        if ~isempty(f) && ~avertir(f, [])
            e.abonne = [];
        end

    case 'lire'
        t = varargin{1};
        if t < e.t_dernier                        % nouveau lancement : les poussées demandées avant sont oubliées
            e.servie = e.demande;
            e.poussee_fin = -inf;
            e.en_cours = true;
            e.t_ref = t; e.tic_ref = tic;
        end
        e.t_dernier = t;
        if e.rythme && isempty(e.scenario)
            % Temps réel : la simulation attend l'horloge quand elle est en avance. Le rythme de Simulink (Simulation
            % Pacing) coûte du temps de calcul et ralentissait la simulation à 0,8 fois le temps réel ; celui-ci, appelé
            % toutes les 20 ms, ne coûte presque rien. En retard de plus de 0,25 s, on ne rattrape pas : l'horloge est
            % recalée, pour que la simulation ne parte pas en accéléré.
            avance = (t - e.t_ref) - toc(e.tic_ref);
            if avance > 0.002
                pause(avance);
            elseif avance < -0.25
                e.t_ref = t; e.tic_ref = tic;
            end
        end
        if ~isempty(e.scenario)
            S = e.scenario;
            k = find(S(:, 1) <= t + 1e-9, 1, 'last');
            if isempty(k)
                v = zeros(5, 1);
            else
                p = [0; 0];
                if t < S(k, 1) + S(k, 7) - 1e-9, p = S(k, 5:6).'; end
                v = [S(k, 2); S(k, 3); S(k, 4); p];
            end
        else
            if e.demande > e.servie
                e.servie = e.demande;
                e.poussee = e.couple_demande;
                e.poussee_fin = t + e.duree_demande;
            end
            p = [0; 0];
            if t < e.poussee_fin, p = e.poussee; end
            v = [double(e.actif); e.cible; p];
        end
        varargout{1} = v;

    case 'afficher'
        v = varargin{2};
        d = struct('t', varargin{1}, 'angles', v(1:2), 'reference', v(3:4), 'roues', v(5:8), 'reserve', v(9), ...
            'desequilibre', v(10:11), 'poussee', v(12:13));
        e.dernier = d;
        f = e.abonne;                             % l'interface peut rappeler pilotage_banc pendant cet appel (manche déplacé) :
        if ~isempty(f) && ~avertir(f, d)          % e n'est donc jamais recopié en bloc après l'appel
            e.abonne = [];
        end

    otherwise
        error('pilotage_banc:action', 'Action inconnue : %s', action);
end
end

function ok = avertir(f, d)
% Transmet les données du tableau de bord à l'interface. Faux si l'interface est en erreur (fermée, par exemple).
ok = true;
try
    f(d);
catch err
    warning('pilotage_banc:interface', 'Interface de pilotage : %s', err.message);
    ok = false;
end
end

function e = initial()
% donnees du tableau de bord (champ « dernier ») : t (s) ; angles et reference [roulis ; tangage] (°) ; roues : vitesses
% des 4 roues avec leur signe (rad/s) ; reserve des roues (0 à 1) ; desequilibre : centre de masse par rapport au pivot,
% [selon X ; selon Y] (mm) ; poussee en cours [roulis ; tangage] (N.m).
e = struct('actif', false, 'cible', [0; 0], 'demande', 0, 'servie', 0, 'couple_demande', [0; 0], 'duree_demande', 0, ...
    'poussee', [0; 0], 'poussee_fin', -inf, 't_dernier', inf, 'en_cours', false, 'scenario', [], 'abonne', [], 'dernier', [], ...
    'rythme', false, 't_ref', 0, 'tic_ref', tic);
end

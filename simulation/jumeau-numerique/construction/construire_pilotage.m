function construire_pilotage(fichier)
% Ajoute au modèle jumeau_banc_rw.slx ce qu'il faut pour le piloter depuis l'interface pilotage/pilote_banc.m.
% À lancer après construire_commande_haut_niveau.m (qui donne à la Référence son entrée « manche »).
%
% Ce que le script fait :
%   - « Interface de pilotage » : lit le manche et les poussées de l'interface (pilotage/pilotage_banc.m) ;
%   - « Poussée d'essai » : poussée programmée (perturbation_...) plus poussées de l'interface, envoyée au procédé ;
%   - procédé : une seconde entrée « poussée (N.m) », appliquée par les deux jumeaux (le banc réel l'ignorera) ; le jumeau
%     Webots la reçoit à la fin de sa trame de commande (21 octets au lieu des 13 de l'ESP32) ;
%   - « Tableau de bord » : envoie l'état du banc à l'interface, toutes les T_affichage secondes ;
%   - chemin du dossier pilotage, rappels de début et de fin de simulation, réglages envoyés à Webots (51 valeurs).

if nargin < 1
    fichier = fullfile(fileparts(fileparts(mfilename('fullpath'))), 'jumeau_banc_rw.slx');
end
[~, nom] = fileparts(fichier);
load_system(fichier);
parametres(nom);
rappels(nom);
procede([nom '/Procédé']);
niveau_haut(nom);
save_system(nom, fichier);
close_system(nom, 0);
fprintf('pilotage en place : %s\n', fichier);
end

%% ===================================================================== réglages et rappels
function parametres(nom)
mws = get_param(nom, 'ModelWorkspace');
code = mws.MATLABCode;
r = '(?m)T_pont; t_lacher; k_main; c_main; perturbation_t; perturbation_duree; perturbation_couple\(:\)\];[^\n]*';
if ~isempty(regexp(code, r, 'once'))
    code = regexprep(code, r, 'T_pont; t_lacher; k_main; c_main];   % 51 valeurs envoyées au jumeau Webots au lancement');
end
code = regexprep(code, '(?m)^(perturbation_couple = [^\n]*% N\.m, couple de la poussée sur \[roulis tangage\]) \(0 : aucune\)', ...
    '$1, programmée (0 : aucune ; l''interface de pilotage en ajoute)');
mws.MATLABCode = code;
mws.reload;
end

function rappels(nom)
for f = {'PostLoadFcn', 'CloseFcn'}
    c = get_param(nom, f{1});
    if ~contains(c, 'pilotage')
        c = strrep(c, 'fullfile(d, ''liaison''))', 'fullfile(d, ''liaison''), fullfile(d, ''pilotage''))');
        set_param(nom, f{1}, c);
    end
end
c = get_param(nom, 'StartFcn');
if ~contains(c, 'pilotage_banc')
    set_param(nom, 'StartFcn', [c newline 'pilotage_banc(''depart'');   % interface de pilotage : nouveau lancement']);
end
c = get_param(nom, 'StopFcn');
if ~contains(c, 'pilotage_banc')
    set_param(nom, 'StopFcn', [c newline 'pilotage_banc(''fin'');']);
end
d = fileparts(get_param(nom, 'FileName'));
addpath(fullfile(d, 'pilotage'));
end

%% ===================================================================== procédé : entrée de poussée
function procede(p)
if isempty(find_system(p, 'SearchDepth', 1, 'BlockType', 'Inport', 'Name', 'poussée (N.m)'))
    ajouter(p, 'simulink/Ports & Subsystems/In1', 'poussée (N.m)', [30 163 60 177]);
end
simscape([p '/Jumeau Simscape']);
webots([p '/Jumeau Webots']);
end

function simscape(s)
if ~isempty(find_system(s, 'SearchDepth', 1, 'BlockType', 'Inport', 'Name', 'poussée (N.m)'))
    return
end
m = 'Mécanique (CAO version 3)';
ajouter(s, 'simulink/Ports & Subsystems/In1', 'poussée (N.m)', [-45 268 -15 282]);
mm = [s '/' m];
ajouter(mm, 'simulink/Ports & Subsystems/In1', 'poussée (N.m)', [240 568 270 582]);
t = [mm '/Poussée et tenue à la main'];
delete_line(t, 'Début de la poussée/1', 'Couple extérieur/2');
delete_line(t, 'Fin de la poussée/1', 'Couple extérieur/3');
delete_block([t '/Début de la poussée']);
delete_block([t '/Fin de la poussée']);
set_param([t '/Couple extérieur'], 'Inputs', '++');
ajouter(t, 'simulink/Ports & Subsystems/In1', 'poussée (N.m)', [530 368 560 382]);
relier(t, 'poussée (N.m)/1', 'Couple extérieur/2');
a = find_system(t, 'SearchDepth', 1, 'FindAll', 'on', 'Type', 'annotation');
for k = 1:numel(a)
    x = get_param(a(k), 'Text');
    if contains(x, 'Poussée :')
        x = regexprep(x, 'Poussée :[^\n]*', ['Poussée : couple d''essai venu du bloc « Poussée d''essai » du niveau haut (poussée programmée et ' ...
            'poussées de l''interface de pilotage).']);
        set_param(a(k), 'Text', x);
    end
end
relier(mm, 'poussée (N.m)/1', 'Poussée et tenue à la main/3');
relier(s, 'poussée (N.m)/1', [m '/2']);
end

function webots(s)
if ~isempty(find_system(s, 'SearchDepth', 1, 'BlockType', 'Inport', 'Name', 'poussée (N.m)'))
    return
end
ajouter(s, 'simulink/Ports & Subsystems/In1', 'poussée (N.m)', [30 453 60 467]);
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Poussée toutes les T_pont', [120 445 180 475], 'SampleTime', 'T_pont');
script_fonction([s '/Trame de commande'], {
'function trame = trame_commande(imp, poussee)'
'% Trame de commande : celle de l''ESP32 du banc réel (A5 5A, 4 impulsions en µs en uint16, drapeaux, numéro), suivie, pour'
'% le jumeau seulement, de la poussée d''essai sur [roulis ; tangage] (2 nombres en simple précision, N.m), puis la somme.'
'persistent seq'
'if isempty(seq), seq = 0; end'
't = zeros(21, 1, ''uint8'');'
't(1) = uint8(165); t(2) = uint8(90);'
'u = uint16(max(0, min(65535, round(imp(:)))));'
't(3:10) = typecast(u, ''uint8'');'
't(11) = uint8(1);                              % bit 0 : marche'
't(12) = uint8(seq);'
't(13:20) = typecast(single(poussee(:)), ''uint8'');'
't(21) = uint8(mod(sum(double(t(1:20))), 256));'
'seq = mod(seq + 1, 256);'
'trame = t;'
}, {});
relier(s, 'poussée (N.m)/1', 'Poussée toutes les T_pont/1');
relier(s, 'Poussée toutes les T_pont/1', 'Trame de commande/2');
note(s, [30 620], {'Trame de commande du jumeau : les 13 octets de l''ESP32, plus la poussée d''essai (8 octets) avant la somme de contrôle, soit 21 octets.'});
end

%% ===================================================================== niveau haut
function niveau_haut(nom)
if ~isempty(find_system(nom, 'SearchDepth', 1, 'Name', 'Interface de pilotage'))
    return
end
% référence : entrée du manche
set_param([nom '/Référence'], 'Position', [110 185 230 265]);
ph = get_param([nom '/Référence'], 'PortHandles');
c = get_param(ph.Inport(1), 'Position');
depuis(nom, 'manche', [c(1) - 60 c(2) - 10 c(1) - 10 c(2) + 10], 'Référence/1');
% interface de pilotage, poussée d'essai, tableau de bord
b = sous_systeme(nom, 'Interface de pilotage', [70 400 230 470]);
interface(b);
vers(nom, 'Interface de pilotage/1', 'manche', [270 413 340 433], true);
b = sous_systeme(nom, 'Poussée d''essai', [400 425 560 470]);
poussee(b);
relier(nom, 'Interface de pilotage/2', 'Poussée d''essai/1', 'poussee_manche');
vers(nom, 'Poussée d''essai/1', 'poussee', [600 437 680 457], true);
vers(nom, 'Référence/1', 'consigne', [130 290 200 310]);
b = sous_systeme(nom, 'Tableau de bord', [880 390 1040 490]);
tableau(b);
depuis(nom, 'etat', [780 405 850 425], 'Tableau de bord/1');
depuis(nom, 'consigne', [780 430 850 450], 'Tableau de bord/2');
depuis(nom, 'poussee', [780 455 850 475], 'Tableau de bord/3');
% procédé : entrée de poussée
ph = get_param([nom '/Procédé'], 'PortHandles');
c = get_param(ph.Inport(2), 'Position');
depuis(nom, 'poussee', [c(1) - 75 c(2) - 10 c(1) - 15 c(2) + 10], 'Procédé/2');
zone(nom, 'INTERFACE DE PILOTAGE ET ESSAIS', [40 370 1080 505], '[0.93 0.91 1.00]');
% texte du niveau haut
a = find_system(nom, 'FindAll', 'on', 'SearchDepth', 1, 'Type', 'annotation');
for k = 1:numel(a)
    t = get_param(a(k), 'Text');
    if contains(t, 'Toute la chaîne est remplie') && ~contains(t, 'pilote_banc')
        lignes = strsplit(t, newline);
        j = find(contains(lignes, 'Toute la chaîne est remplie'), 1);
        lignes = [lignes(1:j), {'Interface de pilotage : taper pilote_banc dans MATLAB. Manche, poussées, choix du jumeau, état du banc en direct.'}, lignes(j + 1:end)];
        set_param(a(k), 'Text', strjoin(lignes, newline));
        p = get_param(a(k), 'Position');
        set_param(a(k), 'Position', [p(1) p(2) + 10 p(3) p(4) + 28]);
    end
end
end

function interface(s)
ajouter(s, 'simulink/Sources/Digital Clock', 'Temps', [30 48 90 72], 'SampleTime', 'T_chn');
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Lecture de l''interface', [160 30 340 110]);
script_fonction(fn, {
'function [manche, poussee] = lecture(t)'
'% Lit l''interface de pilotage (pilotage/pilotage_banc.m) : manche = [actif ; roulis demandé (°) ; tangage demandé (°)],'
'% poussee = poussée en cours sur [roulis ; tangage] (N.m). Sans interface ouverte : manche inactif, aucune poussée.'
'coder.extrinsic(''pilotage_banc'');'
's = zeros(5, 1);'
's = pilotage_banc(''lire'', t);'
'manche = s(1:3);'
'poussee = s(4:5);'
}, {});
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'manche', [420 48 450 62]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'poussée du manche (N.m)', [420 88 450 102]);
relier(s, 'Temps/1', 'Lecture de l''interface/1');
relier(s, 'Lecture de l''interface/1', 'manche/1');
relier(s, 'Lecture de l''interface/2', 'poussée du manche (N.m)/1');
note(s, [30 160], {'Lit l''interface de pilotage (pilotage/pilote_banc.m, échange par pilotage/pilotage_banc.m) à chaque période de la commande.', ...
    'manche = [actif ; roulis demandé ; tangage demandé] (°) ; poussée en cours sur [roulis ; tangage] (N.m).', ...
    'Interface fermée : le manche est inactif (la référence programmée s''applique) et il n''y a aucune poussée.'});
set_param(s, 'Description', 'Lit le manche et les poussées de l''interface de pilotage.');
end

function poussee(s)
ajouter(s, 'simulink/Sources/Step', 'Début de la poussée programmée', [100 30 130 60], 'Time', 'perturbation_t', 'Before', '[0; 0]', ...
    'After', 'perturbation_couple(:)', 'SampleTime', '0');
ajouter(s, 'simulink/Sources/Step', 'Fin de la poussée programmée', [100 85 130 115], 'Time', 'perturbation_t + perturbation_duree', 'Before', '[0; 0]', ...
    'After', '-perturbation_couple(:)', 'SampleTime', '0');
ajouter(s, 'simulink/Ports & Subsystems/In1', 'poussée du manche (N.m)', [100 143 130 157]);
ajouter(s, 'simulink/Math Operations/Sum', 'Poussée', [220 30 240 160], 'Inputs', '+++', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'poussée (N.m)', [300 88 330 102]);
relier(s, 'Début de la poussée programmée/1', 'Poussée/1');
relier(s, 'Fin de la poussée programmée/1', 'Poussée/2');
relier(s, 'poussée du manche (N.m)/1', 'Poussée/3');
relier(s, 'Poussée/1', 'poussée (N.m)/1');
note(s, [30 220], {'Poussée sur [roulis ; tangage] (N.m), envoyée au procédé : la poussée programmée (perturbation_t, perturbation_duree,', ...
    'perturbation_couple) plus les poussées demandées par l''interface de pilotage. Le banc réel l''ignorera : on le pousse avec le doigt.'});
set_param(s, 'Description', 'Poussée d''essai : programmée et demandée par l''interface, envoyée au procédé.');
end

function tableau(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'état', [30 63 60 77]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'consigne', [30 163 60 177]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'poussée (N.m)', [30 253 60 267]);
ajouter(s, 'simulink/Signal Routing/Bus Selector', 'État', [120 30 125 130], 'OutputSignals', 'angles_deg,vitesses_roues,reserve_roues,desequilibre_mm', 'ShowName', 'off');
ajouter(s, 'simulink/Signal Routing/Bus Selector', 'Consigne', [120 155 125 185], 'OutputSignals', 'angles_ref_deg', 'ShowName', 'off');
ajouter(s, 'simulink/Sources/Digital Clock', 'Temps', [100 300 160 320], 'SampleTime', 'T_affichage');
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Envoi à l''interface', [280 20 460 330]);
script_fonction(fn, {
'function envoi(angles_deg, roues, reserve, desequilibre_mm, reference_deg, poussee, t)'
'% Envoie l''état du banc à l''interface de pilotage (pilotage/pilotage_banc.m), toutes les T_affichage secondes :'
'% angles et référence [roulis ; tangage] (°), vitesses des 4 roues avec leur signe (rad/s), réserve des roues (0 à 1),'
'% centre de masse par rapport au pivot [selon X ; selon Y] (mm), poussée en cours (N.m).'
'coder.extrinsic(''pilotage_banc'');'
'pilotage_banc(''afficher'', t, [angles_deg(:); reference_deg(:); roues(:); reserve; desequilibre_mm(:); poussee(:)]);'
}, {});
cadencer(fn, 'T_affichage');
relier(s, 'état/1', 'État/1');
relier(s, 'consigne/1', 'Consigne/1');
for k = 1:4
    relier(s, sprintf('État/%d', k), sprintf('Envoi à l''interface/%d', k));
end
relier(s, 'Consigne/1', 'Envoi à l''interface/5');
relier(s, 'poussée (N.m)/1', 'Envoi à l''interface/6');
relier(s, 'Temps/1', 'Envoi à l''interface/7');
note(s, [30 380], {'Tableau de bord : l''état du banc envoyé à l''interface de pilotage toutes les T_affichage secondes (0,1 s).', ...
    'Il n''utilise que l''état donné par la Perception : il marchera de la même façon avec le banc réel.'});
set_param(s, 'Description', 'Tableau de bord : envoie l''état du banc à l''interface de pilotage.');
end

%% ===================================================================== outils
function b = ajouter(s, src, n, pos, varargin)
b = [s '/' strrep(n, '/', '//')];
add_block(src, b, 'Position', pos, varargin{:});
end

function b = sous_systeme(s, n, pos)
b = [s '/' n];
add_block('built-in/Subsystem', b, 'Position', pos);
set_param(b, 'ContentPreviewEnabled', 'off');
end

function l = relier(s, src, dst, nomsignal)
l = add_line(s, src, dst, 'autorouting', 'smart');
if nargin > 3, set_param(l, 'Name', nomsignal); end
end

function vers(s, src, etiquette, pos, enregistrer)
n = nom_libre(s, ['Goto ' etiquette]);
ajouter(s, 'simulink/Signal Routing/Goto', n, pos, 'GotoTag', etiquette, 'ShowName', 'off');
l = add_line(s, src, [n '/1'], 'autorouting', 'smart');
ph = get_param(l, 'SrcPortHandle');
if isempty(get_param(ph, 'Name')), set_param(ph, 'Name', etiquette); end
if nargin > 4 && enregistrer, set_param(ph, 'DataLogging', 'on'); end
end

function n = depuis(s, etiquette, pos, dst)
n = nom_libre(s, ['From ' etiquette]);
ajouter(s, 'simulink/Signal Routing/From', n, pos, 'GotoTag', etiquette, 'ShowName', 'off');
if ~isempty(dst), add_line(s, [n '/1'], dst, 'autorouting', 'smart'); end
end

function n = nom_libre(s, base)
n = base; k = 1;
while ~isempty(find_system(s, 'SearchDepth', 1, 'Name', n))
    k = k + 1; n = sprintf('%s %d', base, k);
end
end

function script_fonction(blk, lignes, params)
ch = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', blk);
ch.Script = strjoin(lignes, newline);
for k = 1:numel(params)
    d = ch.find('-isa', 'Stateflow.Data', 'Name', params{k});
    d.Scope = 'Parameter';
end
end

function cadencer(blk, periode)
ch = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', blk);
ch.ChartUpdate = 'DISCRETE';
ch.SampleTime = periode;
end

function zone(s, titre, pos, couleur)
a = add_block('built-in/Area', [s '/' strrep(titre, '/', '//')], 'Position', pos);
set_param(a, 'BackgroundColor', couleur, 'FontSize', '12', 'FontWeight', 'bold');
end

function note(s, xy, lignes)
a = Simulink.Annotation(s, strjoin(lignes, newline));
a.Position = [xy(1) xy(2) xy(1) + 900 xy(2) + 18 * numel(lignes)];
a.FontSize = 11;
a.HorizontalAlignment = 'left';
end

% Construit jumeau_banc_rw.slx : la commande du banc de stabilisation (version 3), rangée comme dans le cours de
% robotique avancée (référence, commande haut niveau, conversion, commande bas niveau, procédé, perception), avec un
% procédé à variantes : jumeau Simscape ou jumeau Webots. À cette étape, seul le procédé est rempli ; les blocs de
% commande sont vides et les 4 ESC se pilotent à la main depuis le pupitre.
% Entrée : cao_jumeau.json (preparer_cao.py). Sortie : ../jumeau_banc_rw.slx, paramètres dans son Model Workspace.
% Usage : matlab -batch "construire_simulink"   (depuis ce dossier)
ici = fileparts(mfilename('fullpath'));
dossier = fileparts(ici);
cao = jsondecode(fileread(fullfile(ici, 'cao_jumeau.json')));
nom = 'jumeau_banc_rw';
if bdIsLoaded(nom), close_system(nom, 0); end
fichier = fullfile(dossier, [nom '.slx']);
if exist(fichier, 'file')
    % Le modèle contient maintenant du travail fait à la main (procédé réajusté, commande bas niveau) : ce script
    % repart de zéro et le perdrait. Il ne s'exécute donc que sur demande explicite, et garde une copie de l'ancien.
    if ~exist('ecraser', 'var') || ~isequal(ecraser, true)
        error('jumeau_banc_rw.slx existe déjà. Ce script le reconstruit de zéro (procédé seul). Pour le faire quand même : ecraser = true; construire_simulink');
    end
    copyfile(fichier, fullfile(dossier, [nom '_avant_reconstruction_' char(datetime('now', 'Format', 'yyyyMMdd_HHmmss')) '.slx']));
    delete(fichier);
end
addpath(fullfile(dossier, 'geometrie'), fullfile(dossier, 'liaison'));
new_system(nom);
load_system('sm_lib'); load_system('nesl_utility'); load_system('simulink');
pivots = sprintf('%g ', cao.z_pivots); pivots = strtrim(pivots);

%% Paramètres : Model Workspace, code MATLAB enregistré dans le modèle
code = {
'%% Jumeau numérique du banc de stabilisation à 4 roues de réaction (version 3) : paramètres'
'% Ce code est enregistré dans le modèle (Model Explorer > jumeau_banc_rw > Model Workspace).'
'% Origine : (CAO) CAO du banc version 3, (M) mesuré sur le matériel, (F) fiche technique, (Fw) firmware,'
'% (H) hypothèse à mesurer sur le banc. Masses et inerties des pièces : dans chaque bloc de pièce.'
''
'%% Montage de l''essai'
sprintf('pivot_mm = %g;              %% position du pivot de tangage sur le corps : %s mm (CAO : %g)', cao.z_pivot_cao, strrep(pivots, ' ', ', '), cao.z_pivot_cao)
'blocage_roulis = 0;         % goupille de blocage : 1 = axe bloqué à 0°, 0 = axe libre'
'blocage_tangage = 0;'
'angle0_roulis_deg = 2;      % position de départ (mise à 0 si l''axe est bloqué)'
'angle0_tangage_deg = -1;'
'g = 9.81;                   % m/s²'
''
'%% Pupitre : pilotage manuel des 4 ESC'
'essai_t = 1;                % s, instant de l''échelon d''essai ajouté aux curseurs'
'essai_echelon_us = [0 0 0 0];   % µs, échelon d''essai sur chaque ESC (0 : aucun)'
''
'%% Alimentation des ESC'
'V_alim = 12;                % V, alimentation de labo (H : tension réglée)'
''
'%% ESC Brushless 30A bidirectionnels (x4)'
'f_trame_esc = 50;           % Hz, une impulsion toutes les 20 ms (Fw : LEDC 50 Hz)'
'imp_neutre = 1500;          % µs, neutre (testé sur le banc)'
'imp_min = 1000;             % µs (Fw)'
'imp_max = 2000;             % µs (Fw)'
'zone_morte_us = 0;          % µs autour du neutre (H)'
'tau_esc = 2e-3;             % s, temps de réponse de l''ESC (H)'
'armement_actif = 1;         % 1 : l''ESC ne pilote le moteur qu''après t_armement au neutre'
't_armement = 1;             % s (H)'
'fenetre_armement_us = 25;   % µs, écart au neutre accepté pendant l''armement (H)'
'sens_moteurs = [1 1 1 1];   % +1 : au-dessus du neutre, la roue tourne dans le sens +axe (vers l''extérieur) (H : ordre des phases)'
''
'%% Moteurs A2212 1400 KV (x4), modèle équivalent continu'
'KV = 1400;                  % tr/min/V (F)'
'Ke = 60/(2*pi*KV);          % V.s/rad'
'Kt = Ke;                    % N.m/A'
'R_moteur = 0.08;            % ohm (H)'
'L_moteur = 30e-6;           % H (H)'
'f_roue = 5e-6;              % N.m.s/rad, frottement visqueux des roulements du moteur (H)'
''
'%% Cardan'
sprintf('butee_deg = %g;             %% débattement de chaque axe (CAO)', cao.butee_deg)
'k_butee = 20;               % N.m/rad, contact goupille-lumière (H)'
'c_butee = 0.2;              % N.m.s/rad (H)'
'b_cardan = 1e-4;            % N.m.s/rad, frottement des roulements 625 (H)'
'k_cables = 0;               % N.m/rad, raideur des deux câbles vers la table (H)'
''
'%% BNO055 (mode fusion)'
'T_bno = 0.01;               % s, données de fusion à 100 Hz (F)'
'bruit_bno = 1;              % 1 : bruit de mesure, 0 : capteur parfait'
'sigma_angle_deg = 0.05;     % ° (H)'
'sigma_gyro_dps = 0.1;       % °/s (H)'
'sigma_acc = 0.02;           % m/s² (H)'
'R_montage_bno = eye(3);     % axes du capteur dans le repère du dispositif : eye(3) = remappage AXIS_MAP réglé'
'                            % (la carte est tournée de 90° dans la CAO)'
''
'%% Capteurs de vitesse TCRT5000 (x4) : un front à chaque rayon du disque'
sprintf('n_rayons = %d;               %% rayons du disque vus par tour (CAO : disque d'origine)', cao.rayons_disque)
'T_tcrt = 1e-3;              % s, pas de calcul du capteur (les fronts sont datés par interpolation, comme un chronomètre en µs)'
't_arret_tcrt = 0.2;         % s sans front : la vitesse mesurée retombe à 0 (Fw, à fixer)'
''
'%% Pont vers le jumeau Webots (et, plus tard, vers l''ESP32 du banc réel)'
'T_pont = 0.01;              % s, une trame de commande et une trame de télémétrie toutes les 10 ms'
''
'%% Grandeurs dérivées'
sprintf('assert(any(pivot_mm == [%s]), ''pivot_mm : %s (inserts du corps)'');', pivots, strrep(pivots, ' ', ', '))
'q0_deg = [angle0_roulis_deg angle0_tangage_deg] .* ([blocage_roulis blocage_tangage] == 0);'
'config_jumeau = [pivot_mm; blocage_roulis; blocage_tangage; q0_deg(:); V_alim; f_trame_esc; imp_neutre; imp_min; imp_max; ...'
'    zone_morte_us; tau_esc; armement_actif; t_armement; fenetre_armement_us; sens_moteurs(:); Ke; Kt; R_moteur; L_moteur; ...'
'    f_roue; butee_deg; k_butee; c_butee; b_cardan; k_cables; g; T_bno; bruit_bno; sigma_angle_deg; sigma_gyro_dps; ...'
'    sigma_acc; n_rayons; t_arret_tcrt; T_tcrt; R_montage_bno(:); T_pont];   % 48 valeurs envoyées au jumeau Webots au lancement'
};
mws = get_param(nom, 'ModelWorkspace');
mws.DataSource = 'MATLAB Code';
mws.MATLABCode = strjoin(code, newline);
mws.reload;

%% Niveau haut : l'ossature du cours
set_param(nom, 'Solver', 'ode23t', 'StopTime', '10', 'MaxStep', '1e-3', 'RelTol', '1e-4', ...
    'SignalLogging', 'on', 'SignalLoggingName', 'logsout', 'SaveFormat', 'Dataset', 'ReturnWorkspaceOutputs', 'on');
set_param(nom, 'PostLoadFcn', ['d = fileparts(get_param(''' nom ''', ''FileName'')); addpath(fullfile(d, ''geometrie''), fullfile(d, ''liaison'')); clear d']);
set_param(nom, 'StartFcn', strjoin({
    '% Jumeau Webots : au lancement, MATLAB envoie les paramètres du Model Workspace à Webots, qui remet le banc en'
    '% position de départ, puis ouvre la liaison de télémétrie et la liaison de commande (liaison/pont_banc.m).'
    ['if strcmp(get_param(''' nom '/Procédé'', ''LabelModeActiveChoice''), ''Webots'')']
    ['    pont_banc(''ouvrir'', getVariable(get_param(''' nom ''', ''ModelWorkspace''), ''config_jumeau''));']
    'end'}, newline));
set_param(nom, 'StopFcn', 'pont_banc(''fermer'');');
set_param(nom, 'CloseFcn', ['try, d = fileparts(get_param(''' nom ''', ''FileName'')); rmpath(fullfile(d, ''geometrie''), fullfile(d, ''liaison'')); clear d, catch, end']);
y0 = 200; h = 90;
ref = bloc_vide(nom, 'Référence', [70 y0 210 y0 + h], {}, {'consigne (°)', '[0; 0]'}, ...
    {'Référence : consigne de roulis et de tangage au cours du temps.', 'À construire. Pour l''instant : 0° sur les deux axes.'});
hn = bloc_vide(nom, 'Commande haut niveau', [300 y0 460 y0 + h], {'consigne (°)', 'état'}, {'couples des axes (N.m)', '[0; 0]'}, ...
    {'Commande haut niveau : stabilisation de l''inclinaison (roulis, tangage).', 'À construire. Pour l''instant : aucun couple demandé.'});
cv = bloc_vide(nom, 'Conversion', [550 y0 690 y0 + h], {'couples (N.m)'}, {'consignes', '[0; 0; 0; 0]'}, ...
    {'Conversion : répartition des couples des deux axes sur les 4 roues (cos 45°),', 'l''équivalent de (v, omega) vers les deux roues du cours. À construire.'});
bn = bloc_vide(nom, 'Commande bas niveau', [780 y0 940 y0 + h], {'consignes des roues', 'état'}, {'impulsions commandées (µs)', 'imp_neutre * [1; 1; 1; 1]'}, ...
    {'Commande bas niveau : commande de chaque roue avec observateur, sortie en impulsions d''ESC.', 'À construire. Pour l''instant : neutre (1500 µs).'});
pup = [nom '/Pupitre'];
add_block('built-in/Subsystem', pup, 'Position', [1030 y0 1170 y0 + h]);
construire_pupitre(pup);
proc = [nom '/Procédé'];
add_block('simulink/Ports & Subsystems/Variant Subsystem', proc, 'Position', [1270 y0 - 20 1470 y0 + h + 20]);
construire_procede(proc, cao);
is = [nom '/Interface sensorielle'];
add_block('built-in/Subsystem', is, 'Position', [1570 y0 1710 y0 + h]);
construire_interface(is);
per = [nom '/Perception'];
add_block('built-in/Subsystem', per, 'Position', [1800 y0 1940 y0 + h]);
construire_perception(per);
l = add_line(nom, 'Référence/1', 'Commande haut niveau/1'); set_param(l, 'Name', 'consigne');
l = add_line(nom, 'Commande haut niveau/1', 'Conversion/1'); set_param(l, 'Name', 'couples_axes');
l = add_line(nom, 'Conversion/1', 'Commande bas niveau/1'); set_param(l, 'Name', 'consignes_roues');
l = add_line(nom, 'Commande bas niveau/1', 'Pupitre/1'); set_param(l, 'Name', 'imp_commande');
l = add_line(nom, 'Pupitre/1', 'Procédé/1'); set_param(l, 'Name', 'imp'); journaliser(l);
l = add_line(nom, 'Procédé/1', 'Interface sensorielle/1'); set_param(l, 'Name', 'capteurs'); journaliser(l);
l = add_line(nom, 'Interface sensorielle/1', 'Perception/1'); set_param(l, 'Name', 'mesures');
l = add_line(nom, 'Perception/1', 'Commande haut niveau/2', 'autorouting', 'smart'); set_param(l, 'Name', 'etat'); journaliser(l);
add_line(nom, 'Perception/1', 'Commande bas niveau/2', 'autorouting', 'smart');
% affichage
ajouter(nom, 'simulink/Signal Routing/Bus Selector', 'Sel état', [2030 y0 + 10 2035 y0 + 80], 'OutputSignals', 'angles_deg,vitesses_roues');
add_line(nom, 'Perception/1', 'Sel état/1');
ajouter(nom, 'simulink/Signal Routing/Bus Selector', 'Sel réel', [1570 y0 + 190 1575 y0 + 290], ...
    'OutputSignals', 'angles_cardan,roues_tr_min,courants_A');
l = add_line(nom, 'Procédé/2', 'Sel réel/1', 'autorouting', 'smart'); set_param(l, 'Name', 'grandeurs_reelles'); journaliser(l);
ajouter(nom, 'simulink/Math Operations/Gain', 'en rad par s', [1640 y0 + 228 1700 y0 + 252], 'Gain', '2*pi/60');
add_line(nom, 'Sel réel/2', 'en rad par s/1');
ajouter(nom, 'simulink/Sinks/Scope', 'Angles (°)', [2140 y0 - 10 2180 y0 + 50], 'NumInputPorts', '2');
add_line(nom, 'Sel état/1', 'Angles (°)/1');
add_line(nom, 'Sel réel/1', 'Angles (°)/2', 'autorouting', 'smart');
ajouter(nom, 'simulink/Sinks/Scope', 'Roues', [2140 y0 + 90 2180 y0 + 170], 'NumInputPorts', '3');
add_line(nom, 'Sel état/2', 'Roues/1');
add_line(nom, 'en rad par s/1', 'Roues/2', 'autorouting', 'smart');
add_line(nom, 'Sel réel/3', 'Roues/3', 'autorouting', 'smart');
configurer_scope([nom '/Angles (°)'], {'mesuré par le BNO055 : roulis, tangage (°)', 'cardan réel : roulis, tangage (°)'});
configurer_scope([nom '/Roues'], {'vitesse mesurée par les TCRT5000 (rad/s, sans signe)', 'vitesse réelle des roues (rad/s)', 'courant des moteurs (A)'});
zone(nom, 'PLANIFICATION', [40 y0 - 70 240 y0 + h + 40], '[0.85 0.95 0.85]');
zone(nom, 'COMMANDE', [270 y0 - 70 970 y0 + h + 40], '[1.00 0.87 0.87]');
zone(nom, 'PILOTAGE MANUEL', [1000 y0 - 70 1200 y0 + h + 40], '[1.00 0.95 0.80]');
zone(nom, 'PROCÉDÉ', [1240 y0 - 70 1500 y0 + h + 40], '[0.92 0.92 0.92]');
zone(nom, 'PERCEPTION', [1540 y0 - 70 1970 y0 + h + 40], '[0.85 0.90 1.00]');
note(nom, [40 y0 + 330], {'Banc de stabilisation à 4 roues de réaction, version 3 : commande et jumeaux numériques', ...
    'Rangé comme le cours de robotique avancée : référence, commande haut niveau, conversion, commande bas niveau, procédé, perception.', ...
    'À cette étape, seul le PROCÉDÉ est rempli. Les blocs de commande sont vides : on pilote les 4 ESC à la main depuis le Pupitre.', ...
    'Procédé : clic droit sur le bloc > Variant > Label Mode Active Choice : Simscape (calcul dans Simulink) ou Webots (lancer Webots avant).', ...
    'Les deux jumeaux ont la même interface que le banc réel : entrée = 4 impulsions d''ESC en µs ; sorties = BNO055 et 4 vitesses de roue.', ...
    ['Mécanique : CAO du banc version 3, ' num2str(numel(cao.instances)) ' pièces. Paramètres : Model Explorer > Model Workspace.']});

% blocs du niveau haut : pas d'aperçu du contenu, les noms des ports restent lisibles
b = find_system(nom, 'SearchDepth', 1, 'BlockType', 'SubSystem');
for k = 1:numel(b), set_param(b{k}, 'ContentPreviewEnabled', 'off'); end

%% Enregistrement
set_param(nom, 'SimMechanicsOpenEditorOnUpdate', 'on');
set_param(nom, 'EnablePacing', 'on', 'PacingRate', '1');
save_system(nom, fichier);
close_system(nom, 0);
fprintf('modèle enregistré : %s\n', fichier);

%% ===================================================================== ossature
function s = bloc_vide(parent, n, pos, entrees, sortie, texte)
% Sous-système « à construire » : entrées terminées, sortie constante.
s = [parent '/' n];
add_block('built-in/Subsystem', s, 'Position', pos);
for k = 1:numel(entrees)
    e = ajouter(s, 'simulink/Ports & Subsystems/In1', entrees{k}, [30 40 + 60 * (k - 1) 60 54 + 60 * (k - 1)]);
    t = ajouter(s, 'simulink/Sinks/Terminator', sprintf('non utilisé %d', k), [130 37 + 60 * (k - 1) 150 57 + 60 * (k - 1)]); %#ok<NASGU>
    add_line(s, [entrees{k} '/1'], sprintf('non utilisé %d/1', k)); %#ok<NASGU>
    clear e
end
ajouter(s, 'simulink/Sources/Constant', 'à construire', [260 40 380 70], 'Value', sortie{2});
ajouter(s, 'simulink/Ports & Subsystems/Out1', sortie{1}, [460 48 490 62]);
add_line(s, 'à construire/1', [sortie{1} '/1']);
note(s, [30 200], texte);
set_param(s, 'BackgroundColor', '[1 1 1]', 'Description', strjoin(texte, ' '));
end

function construire_pupitre(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'commande (µs)', [30 363 60 377]);
ajouter(s, 'simulink/Sources/Constant', 'un', [30 150 60 180], 'Value', '1');
ajouter(s, 'simulink/Signal Routing/Mux', 'Curseurs', [330 40 335 290], 'Inputs', '4');
for k = 1:4
    b = ajouter(s, 'simulink/Math Operations/Slider Gain', sprintf('ESC %d (µs)', k), [160 45 + 62 * (k - 1) 260 85 + 62 * (k - 1)]);
    set_param(b, 'high', '1700'); set_param(b, 'gain', '1500'); set_param(b, 'low', '1300');
    add_line(s, 'un/1', sprintf('ESC %d (µs)/1', k), 'autorouting', 'smart');
    add_line(s, sprintf('ESC %d (µs)/1', k), sprintf('Curseurs/%d', k));
end
ajouter(s, 'simulink/Sources/Step', 'Échelon d''essai', [330 310 360 340], 'Time', 'essai_t', 'Before', '[0; 0; 0; 0]', 'After', 'essai_echelon_us(:)', 'SampleTime', '0');
ajouter(s, 'simulink/Math Operations/Sum', 'Curseurs + essai', [420 155 440 195], 'Inputs', '++', 'IconShape', 'rectangular');
add_line(s, 'Curseurs/1', 'Curseurs + essai/1'); add_line(s, 'Échelon d''essai/1', 'Curseurs + essai/2', 'autorouting', 'smart');
ajouter(s, 'simulink/Signal Routing/Manual Switch', 'Mode : manuel (haut) ou commande (bas)', [540 160 590 220], 'sw', '1');
add_line(s, 'Curseurs + essai/1', 'Mode : manuel (haut) ou commande (bas)/1', 'autorouting', 'smart');
add_line(s, 'commande (µs)/1', 'Mode : manuel (haut) ou commande (bas)/2', 'autorouting', 'smart');
ajouter(s, 'simulink/Sources/Constant', 'Neutre', [540 280 620 310], 'Value', 'imp_neutre * [1; 1; 1; 1]');
ajouter(s, 'simulink/Signal Routing/Manual Switch', 'Marche (haut) ou arrêt (bas)', [720 180 770 240], 'sw', '1');
add_line(s, 'Mode : manuel (haut) ou commande (bas)/1', 'Marche (haut) ou arrêt (bas)/1', 'autorouting', 'smart');
add_line(s, 'Neutre/1', 'Marche (haut) ou arrêt (bas)/2', 'autorouting', 'smart');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'imp (µs)', [860 203 890 217]);
add_line(s, 'Marche (haut) ou arrêt (bas)/1', 'imp (µs)/1');
note(s, [30 430], {'Pupitre : pilotage manuel des 4 ESC, en attendant la commande.', ...
    'Double-clic sur un curseur ESC k : impulsion de 1300 à 1700 µs (1500 = neutre). Les ESC s''arment après 1 s au neutre.', ...
    'Échelon d''essai : essai_echelon_us (Model Workspace) s''ajoute aux curseurs à t = essai_t, pour des essais reproductibles.', ...
    'Double-clic sur un interrupteur pour le basculer : manuel ou commande ; marche ou arrêt (neutre).'});
end

function construire_interface(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'capteurs', [30 103 60 117]);
ajouter(s, 'simulink/Signal Routing/Bus Selector', 'Registres lus', [130 60 135 160], 'OutputSignals', 'BNO055.euler,BNO055.gyro,vitesses_roues');
add_line(s, 'capteurs/1', 'Registres lus/1');
ajouter(s, 'simulink/Signal Routing/Selector', 'Roulis, tangage', [220 60 290 90], 'Indices', '[2 3]', 'InputPortWidth', '3');
add_line(s, 'Registres lus/1', 'Roulis, tangage/1');
bc = ajouter(s, 'simulink/Signal Routing/Bus Creator', 'Mesures', [400 50 405 170], 'Inputs', '3');
l = add_line(s, 'Roulis, tangage/1', 'Mesures/1', 'autorouting', 'smart'); set_param(l, 'Name', 'angles_deg');
ajouter(s, 'simulink/Signal Attributes/Signal Conversion', 'Gyroscope', [220 105 290 125]);
add_line(s, 'Registres lus/2', 'Gyroscope/1');
l = add_line(s, 'Gyroscope/1', 'Mesures/2', 'autorouting', 'smart'); set_param(l, 'Name', 'gyro_dps');
add_line(s, 'Registres lus/3', 'Mesures/3', 'autorouting', 'smart');   % garde son nom : vitesses_roues
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'mesures', [480 103 510 117]);
add_line(s, 'Mesures/1', 'mesures/1');
set_param(bc, 'Description', 'angles_deg = [roulis; tangage] (°), gyro_dps (°/s, axes du capteur), vitesses_roues (rad/s, sans signe).');
note(s, [30 220], {'Interface sensorielle : ce que l''ESP32 lit sur les capteurs, mis en grandeurs utiles.', ...
    'BNO055 : euler = [cap ; roulis ; tangage] en degrés, gyroscope en °/s. TCRT5000 : vitesse de chaque roue, sans signe.'});
end

function construire_perception(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'mesures', [30 63 60 77]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'état', [260 63 290 77]);
add_line(s, 'mesures/1', 'état/1');
note(s, [30 140], {'Perception : estimation de l''état à partir des mesures (filtrage, signe des vitesses de roue, observateur).', ...
    'À construire. Pour l''instant : l''état est la mesure brute.'});
end

%% ===================================================================== procédé à variantes
function construire_procede(proc, cao)
supprimer_contenu(proc);
set_param(proc, 'VariantControlMode', 'label');
ajouter(proc, 'simulink/Ports & Subsystems/In1', 'imp (µs)', [30 103 60 117]);
ajouter(proc, 'simulink/Ports & Subsystems/Out1', 'capteurs', [560 73 590 87]);
ajouter(proc, 'simulink/Ports & Subsystems/Out1', 'grandeurs réelles', [560 133 590 147]);
sim = [proc '/Jumeau Simscape'];
add_block('built-in/Subsystem', sim, 'Position', [200 60 420 160]);
construire_banc(sim, cao);
set_param(sim, 'VariantControl', 'Simscape');
web = [proc '/Jumeau Webots'];
add_block('built-in/Subsystem', web, 'Position', [200 220 420 320]);
construire_webots(web);
set_param(web, 'VariantControl', 'Webots');
set_param(proc, 'LabelModeActiveChoice', 'Simscape');
end

function construire_webots(s)
N_TELE = 151;
ajouter(s, 'simulink/Ports & Subsystems/In1', 'imp (µs)', [30 393 60 407]);
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Une trame toutes les T_pont', [120 385 180 415], 'SampleTime', 'T_pont');
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Trame de commande', [340 370 480 430]);
script_fonction(fn, {
'function trame = trame_commande(imp)'
'% Trame de commande, la même que pour l''ESP32 du banc réel : A5 5A, 4 impulsions (uint16, µs), drapeaux, numéro, somme.'
'persistent seq'
'if isempty(seq), seq = 0; end'
't = zeros(13, 1, ''uint8'');'
't(1) = uint8(165); t(2) = uint8(90);'
'u = uint16(max(0, min(65535, round(imp(:)))));'
't(3:10) = typecast(u, ''uint8'');'
't(11) = uint8(1);                              % bit 0 : marche'
't(12) = uint8(seq);'
't(13) = uint8(mod(sum(double(t(1:12))), 256));'
'seq = mod(seq + 1, 256);'
'trame = t;'
}, {});
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Envoi au procédé', [560 370 700 430]);
script_fonction(fn, {
'function envoi(trame)'
'% Envoie la trame de commande au procédé (liaison/pont_banc.m).'
'coder.extrinsic(''pont_banc'');'
'pont_banc(''ecrire'', trame);'
}, {});
add_line(s, 'imp (µs)/1', 'Une trame toutes les T_pont/1');
add_line(s, 'Une trame toutes les T_pont/1', 'Trame de commande/1');
add_line(s, 'Trame de commande/1', 'Envoi au procédé/1');
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Réception du procédé', [30 100 150 160]);
script_fonction(fn, {
'function trame = reception()'
'% Attend la trame de télémétrie du procédé (liaison/pont_banc.m) : Simulink et le jumeau restent au même instant.'
'coder.extrinsic(''pont_banc'');'
sprintf('trame = zeros(%d, 1, ''uint8'');', N_TELE)
'trame = pont_banc(''lire'');'
}, {});
cadencer(fn, 'T_pont');
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Décodage de la télémétrie', [220 30 400 290]);
script_fonction(fn, {
'function [euler, gyro, quat, acc, w_mes, angles, vitesses, tr_min, courants, couples, tensions, rapports, i_alim, ok] = decodage(trame)'
'% Trame de télémétrie, la même que celle de l''ESP32 du banc réel : B5 5B, temps (ms), état, numéro,'
'% BNO055 en unités de ses registres (1/16 °, 1/16 °/s, 2^-14, 0,01 m/s²), 4 vitesses de roue (rad/s), somme.'
'% Le jumeau Webots ajoute ses grandeurs réelles (25 nombres en simple précision).'
'ok = double(trame(1) == 181 && trame(2) == 91 && mod(sum(double(trame(1:50))), 256) == double(trame(51)));'
'euler = double(typecast(trame(9:14), ''int16'')) / 16;'
'gyro = double(typecast(trame(15:20), ''int16'')) / 16;'
'quat = double(typecast(trame(21:28), ''int16'')) / 2^14;'
'acc = double(typecast(trame(29:34), ''int16'')) / 100;'
'w_mes = double(typecast(trame(35:50), ''single''));'
'v = double(typecast(trame(52:151), ''single''));'
'angles = v(1:2); vitesses = v(3:4); tr_min = v(5:8) * 60 / (2*pi);'
'courants = v(9:12); couples = v(13:16); tensions = v(17:20); rapports = v(21:24); i_alim = v(25);'
}, {});
typer_entree(fn, 'trame', 'uint8', sprintf('[%d 1]', N_TELE));
add_line(s, 'Réception du procédé/1', 'Décodage de la télémétrie/1');
bno = ajouter(s, 'simulink/Signal Routing/Bus Creator', 'Registres', [500 30 505 110], 'Inputs', '4');
n = {'euler', 'gyro', 'quat', 'acc'};
for k = 1:4
    l = add_line(s, sprintf('Décodage de la télémétrie/%d', k), sprintf('Registres/%d', k), 'autorouting', 'smart'); set_param(l, 'Name', n{k});
end
ajouter(s, 'simulink/Signal Routing/Bus Creator', 'Capteurs', [600 50 605 130], 'Inputs', '2');
l = add_line(s, 'Registres/1', 'Capteurs/1', 'autorouting', 'smart'); set_param(l, 'Name', 'BNO055');
l = add_line(s, 'Décodage de la télémétrie/5', 'Capteurs/2', 'autorouting', 'smart'); set_param(l, 'Name', 'vitesses_roues');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'capteurs', [680 83 710 97]);
add_line(s, 'Capteurs/1', 'capteurs/1');
ajouter(s, 'simulink/Signal Routing/Bus Creator', 'Mesures réelles', [600 150 605 290], 'Inputs', '8');
n = {'angles_cardan', 'vitesses_cardan', 'roues_tr_min', 'courants_A', 'couples_Nm', 'tensions_V', 'rapports_cycliques', 'courant_alim_A'};
for k = 1:8
    l = add_line(s, sprintf('Décodage de la télémétrie/%d', k + 5), sprintf('Mesures réelles/%d', k), 'autorouting', 'smart'); set_param(l, 'Name', n{k});
end
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'grandeurs réelles', [680 213 710 227]);
add_line(s, 'Mesures réelles/1', 'grandeurs réelles/1');
ajouter(s, 'simulink/Sinks/Display', 'Trame valide (1)', [500 300 560 325]);
add_line(s, 'Décodage de la télémétrie/14', 'Trame valide (1)/1', 'autorouting', 'smart');
set_param(bno, 'Description', 'Ce que lit l''ESP32 par I2C : euler = [cap roulis tangage] (°), gyro (°/s), quat, acc (m/s²).');
note(s, [30 500], {'Jumeau Webots : le même banc, calculé par Webots (physique ODE, vue 3D). Lancer Webots avant la simulation :', ...
    'ouvrir webots/worlds/banc_stabilisation.wbt, puis lancer ce modèle. Webots avance au rythme de Simulink, 10 ms par trame.', ...
    'Liaison locale (liaison/pont_banc.m) : télémétrie reçue sur le port 5005, commande envoyée sur le port 5006 ; ce sont les trames', ...
    'du banc réel : il suffira de remplacer Webots par l''ESP32.', ...
    'Au lancement, les paramètres du Model Workspace (ESC, moteurs, cardan, capteurs, montage de l''essai) sont envoyés à Webots', ...
    '(port 5007, rappel StartFcn du modèle) : MATLAB reste la seule source des réglages. Webots remet alors le banc en position de départ.'});
end

%% ===================================================================== jumeau Simscape
function construire_banc(s, cao)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'imp (µs)', [30 143 60 157]);
esc = [s '/ESC x4'];
add_block('built-in/Subsystem', esc, 'Position', [130 110 260 190]);
construire_esc(esc);
mot = [s '/Moteurs A2212 x4'];
add_block('built-in/Subsystem', mot, 'Position', [380 110 510 190]);
construire_moteurs(mot);
meca = [s '/Mécanique (CAO version 3)'];
add_block('built-in/Subsystem', meca, 'Position', [560 90 720 290]);
construire_mecanique(meca, cao);
bno = [s '/Capteur BNO055'];
add_block('built-in/Subsystem', bno, 'Position', [820 200 950 300]);
construire_bno(bno);
tc = [s '/Capteurs de vitesse TCRT5000 x4'];
add_block('built-in/Subsystem', tc, 'Position', [820 340 950 400]);
construire_tcrt(tc);
add_line(s, 'imp (µs)/1', 'ESC x4/1');
l = add_line(s, 'ESC x4/1', 'Moteurs A2212 x4/1', 'autorouting', 'smart'); set_param(l, 'Name', 'V_moteurs');
l = add_line(s, 'Moteurs A2212 x4/1', 'Mécanique (CAO version 3)/1', 'autorouting', 'smart'); set_param(l, 'Name', 'Cm');
l = add_line(s, 'Mécanique (CAO version 3)/1', 'Moteurs A2212 x4/2', 'autorouting', 'smart'); set_param(l, 'Name', 'omega_roues');
for k = 1:3
    add_line(s, sprintf('Mécanique (CAO version 3)/%d', k + 3), sprintf('Capteur BNO055/%d', k), 'autorouting', 'smart');
end
add_line(s, 'Mécanique (CAO version 3)/7', 'Capteurs de vitesse TCRT5000 x4/1', 'autorouting', 'smart');
ajouter(s, 'simulink/Signal Routing/Bus Creator', 'Capteurs', [1040 240 1045 380], 'Inputs', '2');
l = add_line(s, 'Capteur BNO055/1', 'Capteurs/1', 'autorouting', 'smart'); set_param(l, 'Name', 'BNO055');
l = add_line(s, 'Capteurs de vitesse TCRT5000 x4/1', 'Capteurs/2', 'autorouting', 'smart'); set_param(l, 'Name', 'vitesses_roues');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'capteurs', [1110 303 1140 317]);
add_line(s, 'Capteurs/1', 'capteurs/1');
% grandeurs réelles
ajouter(s, 'simulink/Math Operations/Gain', 'Conversion en tr par min', [820 95 890 125], 'Gain', '60/(2*pi)');
add_line(s, 'Mécanique (CAO version 3)/1', 'Conversion en tr par min/1', 'autorouting', 'smart');
ajouter(s, 'simulink/Math Operations/Dot Product', 'Courant d''alimentation', [560 430 600 470]);
add_line(s, 'ESC x4/2', 'Courant d''alimentation/1', 'autorouting', 'smart');
add_line(s, 'Moteurs A2212 x4/2', 'Courant d''alimentation/2', 'autorouting', 'smart');
bc = ajouter(s, 'simulink/Signal Routing/Bus Creator', 'Mesures réelles', [1040 20 1045 200], 'Inputs', '8');
liens = {'Mécanique (CAO version 3)/2', 'angles_cardan'; 'Mécanique (CAO version 3)/3', 'vitesses_cardan'; ...
         'Conversion en tr par min/1', 'roues_tr_min'; 'Moteurs A2212 x4/2', 'courants_A'; 'Moteurs A2212 x4/1', 'couples_Nm'; ...
         'ESC x4/1', 'tensions_V'; 'ESC x4/2', 'rapports_cycliques'; 'Courant d''alimentation/1', 'courant_alim_A'};
for k = 1:size(liens, 1)
    l = add_line(s, liens{k, 1}, sprintf('Mesures réelles/%d', k), 'autorouting', 'smart');
    set_param(l, 'Name', liens{k, 2});
end
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'grandeurs réelles', [1110 103 1140 117]);
add_line(s, 'Mesures réelles/1', 'grandeurs réelles/1');
set_param(bc, 'Description', 'Grandeurs du banc réel, sans bruit : ce que le BNO055 et l''ESP32 ne voient pas.');
end

function construire_tcrt(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'angle des roues (rad)', [20 63 50 77]);
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Pas du capteur', [110 55 160 85], 'SampleTime', 'T_tcrt');
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Mesure de la période', [240 40 400 100]);
script_fonction(fn, {
'function w = mesure_periode(theta, n_rayons, T_tcrt, t_arret_tcrt)'
'% Carte TCRT5000 devant le disque : elle change d''état à chaque passage de rayon. L''ESP32 date chaque front et'
'% en tire la vitesse : un pas angulaire de 2 pi / n_rayons divisé par la durée entre deux fronts. Pas de signe.'
'% Le front est daté dans le pas de calcul par interpolation, comme le fait un chronomètre en microsecondes.'
'persistent k_prec th_prec t t_front w_mem'
'pas = 2*pi / n_rayons;'
'th = theta(:);'
'if isempty(k_prec)'
'    k_prec = floor(th / pas); th_prec = th; t = 0; t_front = -inf(4, 1); w_mem = zeros(4, 1);'
'end'
'k = floor(th / pas);'
'for j = 1:4'
'    if k(j) ~= k_prec(j)'
'        if k(j) > k_prec(j), th_f = k(j) * pas; else, th_f = k_prec(j) * pas; end   % dernier rayon franchi'
'        tf = t - T_tcrt + T_tcrt * (th_f - th_prec(j)) / (th(j) - th_prec(j));'
'        if isfinite(t_front(j)) && tf > t_front(j)'
'            w_mem(j) = abs(k(j) - k_prec(j)) * pas / (tf - t_front(j));'
'        end'
'        t_front(j) = tf;'
'    elseif t - t_front(j) > t_arret_tcrt'
'        w_mem(j) = 0;'
'    end'
'end'
'k_prec = k; th_prec = th; t = t + T_tcrt;'
'w = w_mem;'
}, {'n_rayons', 'T_tcrt', 't_arret_tcrt'});
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture à chaque trame', [480 55 540 85], 'SampleTime', 'T_pont');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'vitesses mesurées (rad par s)', [620 63 650 77]);
add_line(s, 'angle des roues (rad)/1', 'Pas du capteur/1');
add_line(s, 'Pas du capteur/1', 'Mesure de la période/1');
add_line(s, 'Mesure de la période/1', 'Lecture à chaque trame/1');
add_line(s, 'Lecture à chaque trame/1', 'vitesses mesurées (rad par s)/1');
note(s, [20 160], {'TCRT5000 : un capteur par roue, sur sa potence, devant la face extérieure du disque. Il voit passer les 4 rayons.', ...
    'Vitesse = (2 pi / 4) / durée entre deux fronts, sans signe ; retour à 0 après t_arret_tcrt sans front.', ...
    'La valeur est lue toutes les T_pont (10 ms), comme dans la trame de télémétrie de l''ESP32.'});
end

function construire_esc(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'imp (µs)', [20 83 50 97]);
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture des trames (50 Hz)', [100 75 160 105], 'SampleTime', '1/f_trame_esc');
ajouter(s, 'simulink/Discontinuities/Saturation', 'Plage 1000-2000 µs', [240 75 300 105], 'UpperLimit', 'imp_max', 'LowerLimit', 'imp_min');
ajouter(s, 'simulink/Math Operations/Bias', 'Écart au neutre', [370 75 430 105], 'Bias', '-imp_neutre');
ajouter(s, 'simulink/Discontinuities/Dead Zone', 'Zone morte', [490 75 550 105], 'UpperValue', 'zone_morte_us', 'LowerValue', '-zone_morte_us');
ajouter(s, 'simulink/Math Operations/Gain', 'Rapport cyclique', [610 75 680 105], 'Gain', '1/(imp_max - imp_neutre)');
ajouter(s, 'simulink/Math Operations/Product', 'x armé', [740 72 770 118]);
ajouter(s, 'simulink/Math Operations/Gain', 'Sens de rotation', [830 80 900 110], 'Gain', 'sens_moteurs(:)', 'Multiplication', 'Element-wise(K.*u)');
ajouter(s, 'simulink/Math Operations/Gain', 'x V_alim', [970 80 1030 110], 'Gain', 'V_alim');
ajouter(s, 'simulink/Math Operations/Sum', 'e', [1080 80 1100 110], 'Inputs', '+-', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Gain', 'Inverse de tau_esc', [1140 80 1200 110], 'Gain', '1/tau_esc');
ajouter(s, 'simulink/Continuous/Integrator', 'Tension moyenne', [1260 80 1290 110], 'InitialCondition', '[0; 0; 0; 0]');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'V moteurs (V)', [1360 88 1390 102]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'rapports cycliques', [1000 183 1030 197]);
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Armement', [490 160 610 220]);
ajouter(s, 'simulink/Signal Attributes/Signal Specification', 'en colonne', [180 175 230 205], 'Dimensions', '[4 1]');
script_fonction(fn, {
'function arme = armement(imp, armement_actif, t_armement, fenetre_armement_us, imp_neutre, f_trame_esc)'
'% Un ESC ne pilote son moteur qu''après avoir reçu le neutre pendant t_armement depuis sa mise sous tension.'
'% Tant qu''il n''est pas armé, il bipe et laisse le moteur libre.'
'persistent duree etat'
'if isempty(duree), duree = zeros(4, 1); etat = false(4, 1); end'
'au_neutre = abs(imp(:) - imp_neutre) <= fenetre_armement_us;'
'duree = (duree + 1/f_trame_esc) .* au_neutre;'
'etat = etat | (duree >= t_armement) | (armement_actif == 0);'
'arme = double(etat);'
}, {'armement_actif', 't_armement', 'fenetre_armement_us', 'imp_neutre', 'f_trame_esc'});
delete_block([s '/en colonne']);
chaine = {'imp (µs)', 'Lecture des trames (50 Hz)', 'Plage 1000-2000 µs', 'Écart au neutre', 'Zone morte', 'Rapport cyclique'};
for k = 1:numel(chaine) - 1, add_line(s, [chaine{k} '/1'], [chaine{k + 1} '/1']); end
add_line(s, 'Rapport cyclique/1', 'x armé/1');
add_line(s, 'Lecture des trames (50 Hz)/1', 'Armement/1', 'autorouting', 'smart');
add_line(s, 'Armement/1', 'x armé/2', 'autorouting', 'smart');
add_line(s, 'x armé/1', 'Sens de rotation/1');
add_line(s, 'Sens de rotation/1', 'x V_alim/1');
add_line(s, 'Sens de rotation/1', 'rapports cycliques/1', 'autorouting', 'smart');
add_line(s, 'x V_alim/1', 'e/1'); add_line(s, 'e/1', 'Inverse de tau_esc/1'); add_line(s, 'Inverse de tau_esc/1', 'Tension moyenne/1');
add_line(s, 'Tension moyenne/1', 'V moteurs (V)/1');
add_line(s, 'Tension moyenne/1', 'e/2', 'autorouting', 'smart');
note(s, [100 260], {'ESC : à chaque trame (20 ms), l''impulsion fixe le rapport cyclique u = (imp - 1500)/500,', ...
    'puis la tension moyenne appliquée au moteur V = u V_alim, avec le temps de réponse tau_esc.', ...
    'Le courant pris à l''alimentation vaut la somme des u i (rapports cycliques x courants moteurs).'});
end

function construire_moteurs(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'V (V)', [20 63 50 77]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'omega roues (rad par s)', [20 183 50 197]);
ajouter(s, 'simulink/Math Operations/Sum', 'Somme des tensions', [120 55 150 105], 'Inputs', '+--');
ajouter(s, 'simulink/Math Operations/Gain', 'Inverse de L', [200 65 260 95], 'Gain', '1/L_moteur');
ajouter(s, 'simulink/Continuous/Integrator', 'Courant i', [300 65 330 95], 'InitialCondition', '[0; 0; 0; 0]');
ajouter(s, 'simulink/Math Operations/Gain', 'R', [200 125 260 155], 'Gain', 'R_moteur', 'Orientation', 'left');
ajouter(s, 'simulink/Math Operations/Gain', 'Ke (f.c.é.m.)', [120 175 180 205], 'Gain', 'Ke');
ajouter(s, 'simulink/Math Operations/Gain', 'Kt', [400 65 460 95], 'Gain', 'Kt');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'Cm (N.m)', [520 73 550 87]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'i (A)', [520 133 550 147]);
add_line(s, 'V (V)/1', 'Somme des tensions/1');
add_line(s, 'Somme des tensions/1', 'Inverse de L/1'); add_line(s, 'Inverse de L/1', 'Courant i/1'); add_line(s, 'Courant i/1', 'Kt/1');
add_line(s, 'Kt/1', 'Cm (N.m)/1');
add_line(s, 'Courant i/1', 'R/1', 'autorouting', 'smart'); add_line(s, 'R/1', 'Somme des tensions/2', 'autorouting', 'smart');
add_line(s, 'Courant i/1', 'i (A)/1', 'autorouting', 'smart');
add_line(s, 'omega roues (rad par s)/1', 'Ke (f.c.é.m.)/1');
add_line(s, 'Ke (f.c.é.m.)/1', 'Somme des tensions/3', 'autorouting', 'smart');
note(s, [60 250], {'A2212, modèle équivalent continu (comme le TP1), pour chacun des 4 moteurs :', ...
    'L di/dt = V - R i - Ke omega,   Cm = Kt i.', ...
    'omega est la vitesse de la roue par rapport au dispositif ; Cm agit sur la roue et, en réaction, sur le dispositif.', ...
    'Le frottement des roulements (f_roue) et l''inertie (CAO) sont dans la mécanique.'});
end

function construire_bno(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'R capteur', [20 63 50 77]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'omega (repère fixe, rad par s)', [20 143 50 157]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'a (repère fixe, m par s²)', [20 223 50 237]);
for k = 1:3
    n = sprintf('Échantillonnage %d', k);
    ajouter(s, 'simulink/Discrete/Zero-Order Hold', n, [140 55 + 80 * (k - 1) 180 85 + 80 * (k - 1)], 'SampleTime', 'T_bno');
end
add_line(s, 'R capteur/1', 'Échantillonnage 1/1');
add_line(s, 'omega (repère fixe, rad par s)/1', 'Échantillonnage 2/1');
add_line(s, 'a (repère fixe, m par s²)/1', 'Échantillonnage 3/1');
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Fusion BNO055', [240 50 380 250]);
script_fonction(fn, {
'function [euler, gyro, quat, acc] = fusion(R, omega, a, g, R_montage_bno)'
'% Ce que la puce calcule en mode fusion, à partir de l''orientation vraie du capteur.'
'% euler = [cap; roulis; tangage] en degrés (ordre des registres du BNO055), séquence Z-Y-X.'
'Rs = R * R_montage_bno;                     % axes du capteur dans le repère fixe'
'w = Rs.'' * omega;                           % gyroscope : vitesse angulaire dans les axes du capteur'
'f = Rs.'' * (a - [0; 0; -g]);                % accéléromètre : accélération moins la pesanteur'
'cap = atan2(Rs(2, 1), Rs(1, 1));'
'roulis = atan2(Rs(3, 2), Rs(3, 3));'
'tangage = -asin(max(-1, min(1, Rs(3, 1))));'
'euler = [cap; roulis; tangage] * 180/pi;'
'gyro = w * 180/pi;'
'acc = f;'
'% quaternion [w; x; y; z] de Rs'
't = Rs(1, 1) + Rs(2, 2) + Rs(3, 3);'
'if t > 0'
'    q0 = sqrt(1 + t) / 2;'
'    quat = [q0; (Rs(3, 2) - Rs(2, 3)) / (4*q0); (Rs(1, 3) - Rs(3, 1)) / (4*q0); (Rs(2, 1) - Rs(1, 2)) / (4*q0)];'
'else'
'    [~, k] = max([Rs(1, 1) Rs(2, 2) Rs(3, 3)]);'
'    switch k'
'        case 1'
'            r = sqrt(1 + Rs(1, 1) - Rs(2, 2) - Rs(3, 3)) * 2;'
'            quat = [(Rs(3, 2) - Rs(2, 3)) / r; r/4; (Rs(1, 2) + Rs(2, 1)) / r; (Rs(1, 3) + Rs(3, 1)) / r];'
'        case 2'
'            r = sqrt(1 + Rs(2, 2) - Rs(1, 1) - Rs(3, 3)) * 2;'
'            quat = [(Rs(1, 3) - Rs(3, 1)) / r; (Rs(1, 2) + Rs(2, 1)) / r; r/4; (Rs(2, 3) + Rs(3, 2)) / r];'
'        otherwise'
'            r = sqrt(1 + Rs(3, 3) - Rs(1, 1) - Rs(2, 2)) * 2;'
'            quat = [(Rs(2, 1) - Rs(1, 2)) / r; (Rs(1, 3) + Rs(3, 1)) / r; (Rs(2, 3) + Rs(3, 2)) / r; r/4];'
'    end'
'end'
'if quat(1) < 0, quat = -quat; end'
}, {'g', 'R_montage_bno'});
add_line(s, 'Échantillonnage 1/1', 'Fusion BNO055/1');
add_line(s, 'Échantillonnage 2/1', 'Fusion BNO055/2');
add_line(s, 'Échantillonnage 3/1', 'Fusion BNO055/3');
sorties = {'euler', 'Angles d''Euler (pas de 0,0625 °)', 'sigma_angle_deg', '1/16', 1; ...
           'gyro', 'Gyroscope (pas de 0,0625 ° par s)', 'sigma_gyro_dps', '1/16', 2; ...
           'quat', 'Quaternion (pas de 2^-14)', '', '1/2^14', 3; ...
           'acc', 'Accéléromètre (pas de 0,01 m par s²)', 'sigma_acc', '0.01', 4};
y = 40;
for k = 1:size(sorties, 1)
    src = sprintf('Fusion BNO055/%d', sorties{k, 5});
    if ~isempty(sorties{k, 3})
        bru = sprintf('Bruit %s', sorties{k, 1});
        ajouter(s, 'simulink/Sources/Random Number', bru, [400 y + 45 440 y + 75], 'Mean', '[0; 0; 0]', ...
            'Variance', sprintf('(bruit_bno * %s)^2', sorties{k, 3}), 'Seed', sprintf('[%d %d %d]', 10 * k + 1, 10 * k + 2, 10 * k + 3), ...
            'SampleTime', 'T_bno');
        som = sprintf('+ bruit %s', sorties{k, 1});
        ajouter(s, 'simulink/Math Operations/Sum', som, [490 y 510 y + 30], 'Inputs', '++', 'IconShape', 'rectangular');
        add_line(s, src, [som '/1'], 'autorouting', 'smart');
        add_line(s, [bru '/1'], [som '/2'], 'autorouting', 'smart');
        src = [som '/1'];
    end
    ajouter(s, 'simulink/Discontinuities/Quantizer', sorties{k, 2}, [600 y 680 y + 30], 'QuantizationInterval', sorties{k, 4});
    add_line(s, src, [sorties{k, 2} '/1'], 'autorouting', 'smart');
    y = y + 110;
end
bc = ajouter(s, 'simulink/Signal Routing/Bus Creator', 'Registres', [840 40 845 400], 'Inputs', '4');
for k = 1:size(sorties, 1)
    l = add_line(s, [sorties{k, 2} '/1'], sprintf('Registres/%d', k), 'autorouting', 'smart');
    set_param(l, 'Name', sorties{k, 1});
end
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'BNO055', [900 213 930 227]);
add_line(s, 'Registres/1', 'BNO055/1');
set_param(bc, 'Description', 'Ce que lit l''ESP32 par I2C : euler = [cap roulis tangage] (°), gyro (°/s), quat, acc (m/s²).');
note(s, [60 480], {'BNO055 posé sur le plateau, à sa place dans la CAO. Données de fusion à 100 Hz, quantifiées comme les registres.', ...
    'La fusion est supposée parfaite (pas de dérive ni de retard) ; le magnétomètre n''est pas modélisé.', ...
    'Les angles d''Euler suivent la séquence Z-Y-X : en inclinaison combinée, ils diffèrent un peu des angles du cardan.'});
end

function construire_mecanique(s, cao)
ph = @(b) get_param([s '/' b], 'PortHandles');
Y = [160 220];                                 % ligne de la chaîne cinématique
zp = cao.z_pivot_cao;
ajouter(s, 'sm_lib/Frames and Transforms/World Frame', 'Repère fixe (table)', [40 170 80 210]);
ajouter(s, 'sm_lib/Utilities/Mechanism Configuration', 'Pesanteur', [40 40 80 80], 'GravityVector', '[0 0 -g]');
ajouter(s, 'nesl_utility/Solver Configuration', 'Solveur Simscape', [150 40 190 80]);
lier(s, ph('Repère fixe (table)').RConn(1), ph('Pesanteur').RConn(1));
lier(s, ph('Repère fixe (table)').RConn(1), ph('Solveur Simscape').RConn(1));
g = groupe(s, 'Bâti fixe (socle, poteau, fourche)', [100 340 300 400], cao, 'bati', ...
    sprintf('repère fixe : origine au centre du corps au repos pour le pivot à %g mm, Z vers le haut, X roulis, Y tangage', zp));
lier(s, ph('Repère fixe (table)').RConn(1), get_param(g, 'PortHandles').LConn(1));
% roulis
ar = 'Axe de roulis (X), au pivot';
ajouter(s, 'sm_lib/Frames and Transforms/Rigid Transform', ar, [220 Y(1) 280 Y(2)], ...
    'RotationMethod', 'StandardAxis', 'RotationStandardAxis', '+Y', 'RotationAngle', '90', 'RotationAngleUnits', 'deg', ...
    'TranslationMethod', 'Cartesian', 'TranslationCartesianOffset', sprintf('[0 0 %g]', zp), 'TranslationCartesianOffsetUnits', 'mm');
set_param([s '/' ar], 'Description', sprintf('Le centre de rotation (centre du croisillon) est fixe, à %g mm au-dessus de l''origine du repère fixe.', zp));
lier(s, ph('Repère fixe (table)').RConn(1), ph(ar).LConn(1));
articulation(s, 'Roulis', [420 Y(1) 480 Y(2)], 'q0_deg(1)', 'blocage_roulis');
lier(s, ph(ar).RConn(1), ph('Roulis').LConn(1));
ajouter(s, 'sm_lib/Frames and Transforms/Rigid Transform', 'Retour aux axes du banc (roulis)', [620 Y(1) 680 Y(2)], ...
    'RotationMethod', 'StandardAxis', 'RotationStandardAxis', '+Y', 'RotationAngle', '-90', 'RotationAngleUnits', 'deg', 'TranslationMethod', 'None');
lier(s, ph('Roulis').RConn(1), ph('Retour aux axes du banc (roulis)').LConn(1));
g = groupe(s, 'Croisillon (tourne en roulis)', [580 340 780 400], cao, 'croisillon', 'repère : centre du croisillon (pivot), axes du banc tournés du roulis');
lier(s, ph('Retour aux axes du banc (roulis)').RConn(1), get_param(g, 'PortHandles').LConn(1));
% tangage
ajouter(s, 'sm_lib/Frames and Transforms/Rigid Transform', 'Axe de tangage (Y)', [820 Y(1) 880 Y(2)], ...
    'RotationMethod', 'StandardAxis', 'RotationStandardAxis', '+X', 'RotationAngle', '-90', 'RotationAngleUnits', 'deg', 'TranslationMethod', 'None');
lier(s, ph('Retour aux axes du banc (roulis)').RConn(1), ph('Axe de tangage (Y)').LConn(1));
articulation(s, 'Tangage', [1020 Y(1) 1080 Y(2)], 'q0_deg(2)', 'blocage_tangage');
lier(s, ph('Axe de tangage (Y)').RConn(1), ph('Tangage').LConn(1));
ajouter(s, 'sm_lib/Frames and Transforms/Rigid Transform', 'Retour aux axes du banc (tangage)', [1220 Y(1) 1280 Y(2)], ...
    'RotationMethod', 'StandardAxis', 'RotationStandardAxis', '+X', 'RotationAngle', '90', 'RotationAngleUnits', 'deg', 'TranslationMethod', 'None');
lier(s, ph('Tangage').RConn(1), ph('Retour aux axes du banc (tangage)').LConn(1));
g = groupe(s, 'Paliers de tangage', [1140 340 1340 400], cao, 'paliers', 'repère : pivot, axes du dispositif');
lier(s, ph('Retour aux axes du banc (tangage)').RConn(1), get_param(g, 'PortHandles').LConn(1));
ajouter(s, 'sm_lib/Frames and Transforms/Rigid Transform', 'Position du pivot sur le corps', [1420 Y(1) 1480 Y(2)], ...
    'RotationMethod', 'None', 'TranslationMethod', 'Cartesian', 'TranslationCartesianOffset', '[0 0 -pivot_mm]', ...
    'TranslationCartesianOffsetUnits', 'mm');
lier(s, ph('Retour aux axes du banc (tangage)').RConn(1), ph('Position du pivot sur le corps').LConn(1));
set_param([s '/Position du pivot sur le corps'], 'Description', ...
    'Les paliers se vissent sur l''une des 5 paires d''inserts du corps (pivot_mm). Le repère suivant est l''origine du dispositif : centre du corps, à la hauteur des axes des moteurs.');
g = groupe(s, 'Dispositif (corps, étage, électronique, câblage)', [1400 340 1600 400], cao, 'dispositif', 'repère : origine du dispositif (centre du corps, hauteur des axes des moteurs)');
lier(s, ph('Position du pivot sur le corps').RConn(1), get_param(g, 'PortHandles').LConn(1));
% modules de roue
ajouter(s, 'simulink/Ports & Subsystems/In1', 'Cm (N.m)', [1360 693 1390 707]);
ajouter(s, 'simulink/Signal Routing/Demux', 'Demux Cm', [1450 520 1455 880], 'Outputs', '4');
add_line(s, 'Cm (N.m)/1', 'Demux Cm/1');
ajouter(s, 'simulink/Signal Routing/Mux', 'Mux omega', [2080 480 2085 900], 'Inputs', '4');
ajouter(s, 'simulink/Signal Routing/Mux', 'Mux theta', [2180 480 2185 900], 'Inputs', '4');
for k = 1:4
    y = 470 + 130 * (k - 1);
    a = cao.angles_roues.(sprintf('x%d', k));
    m = module_roue(s, k, a, [1720 y 1920 y + 90], cao);
    hm = get_param(m, 'PortHandles');
    lier(s, ph('Position du pivot sur le corps').RConn(1), hm.LConn(1));
    c = sprintf('Cm %d', k);
    ajouter(s, 'nesl_utility/Simulink-PS Converter', c, [1600 y + 55 1630 y + 75], 'Unit', 'N*m');
    add_line(s, sprintf('Demux Cm/%d', k), [c '/1'], 'autorouting', 'smart');
    lier(s, ph(c).RConn(1), hm.LConn(2));
    w = sprintf('omega %d', k);
    ajouter(s, 'nesl_utility/PS-Simulink Converter', w, [1980 y + 15 2010 y + 35], 'Unit', 'rad/s');
    lier(s, hm.RConn(1), ph(w).LConn(1));
    add_line(s, [w '/1'], sprintf('Mux omega/%d', k), 'autorouting', 'smart');
    th = sprintf('theta %d', k);
    ajouter(s, 'nesl_utility/PS-Simulink Converter', th, [1980 y + 55 2010 y + 75], 'Unit', 'rad');
    lier(s, hm.RConn(2), ph(th).LConn(1));
    add_line(s, [th '/1'], sprintf('Mux theta/%d', k), 'autorouting', 'smart');
end
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'omega roues (rad par s)', [2260 583 2290 597]);
add_line(s, 'Mux omega/1', 'omega roues (rad par s)/1', 'autorouting', 'smart');
% angles et vitesses du cardan (mesures parfaites, pour comparer au BNO055)
noms = {'Roulis', 'Tangage'}; xs = [520 1120]; ya = [20 90];
ajouter(s, 'simulink/Signal Routing/Mux', 'Mux angles', [1300 15 1305 115], 'Inputs', '2');
ajouter(s, 'simulink/Signal Routing/Mux', 'Mux vitesses', [1340 40 1345 140], 'Inputs', '2');
for k = 1:2
    a = ['angle ' lower(noms{k})]; v = ['vitesse ' lower(noms{k})];
    ajouter(s, 'nesl_utility/PS-Simulink Converter', a, [xs(k) ya(k) xs(k) + 30 ya(k) + 20], 'Unit', 'deg');
    ajouter(s, 'nesl_utility/PS-Simulink Converter', v, [xs(k) ya(k) + 35 xs(k) + 30 ya(k) + 55], 'Unit', 'deg/s');
    lier(s, ph(noms{k}).RConn(2), ph(a).LConn(1));
    lier(s, ph(noms{k}).RConn(3), ph(v).LConn(1));
    add_line(s, [a '/1'], sprintf('Mux angles/%d', k), 'autorouting', 'smart');
    add_line(s, [v '/1'], sprintf('Mux vitesses/%d', k), 'autorouting', 'smart');
end
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'angles cardan (°)', [1400 58 1430 72]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'vitesses cardan (° par s)', [1400 83 1430 97]);
add_line(s, 'Mux angles/1', 'angles cardan (°)/1'); add_line(s, 'Mux vitesses/1', 'vitesses cardan (° par s)/1');
% BNO055 : repère de la puce et capteur de transformation
ajouter(s, 'sm_lib/Frames and Transforms/Rigid Transform', 'Position du BNO055', [1620 Y(1) 1680 Y(2)], ...
    'RotationMethod', 'None', 'TranslationMethod', 'Cartesian', 'TranslationCartesianOffset', mat2str(cao.bno_mm', 6), ...
    'TranslationCartesianOffsetUnits', 'mm');
set_param([s '/Position du BNO055'], 'Description', 'Centre de la carte GY-BNO055 dans la CAO (RW-32), dans le repère du dispositif.');
lier(s, ph('Position du pivot sur le corps').RConn(1), ph('Position du BNO055').LConn(1));
ajouter(s, 'sm_lib/Frames and Transforms/Transform Sensor', 'Mouvement du BNO055', [1820 Y(1) 1880 Y(2)], ...
    'MeasurementFrame', 'World', 'SenseR', 'on', 'SenseOmega', 'on', 'SenseXYZDDot', 'on');
lier(s, ph('Repère fixe (table)').RConn(1), ph('Mouvement du BNO055').LConn(1));
lier(s, ph('Position du BNO055').RConn(1), ph('Mouvement du BNO055').RConn(1));
sorties = {'R du capteur', '1', 'R capteur'; 'omega du capteur', 'rad/s', 'omega capteur (rad par s)'; 'a du capteur', 'm/s^2', 'a capteur (m par s²)'};
for k = 1:3
    ajouter(s, 'nesl_utility/PS-Simulink Converter', sorties{k, 1}, [1980 110 + 50 * k 2010 130 + 50 * k], 'Unit', sorties{k, 2});
    lier(s, ph('Mouvement du BNO055').RConn(k + 1), ph(sorties{k, 1}).LConn(1));
    ajouter(s, 'simulink/Ports & Subsystems/Out1', sorties{k, 3}, [2140 113 + 50 * k 2170 127 + 50 * k], 'Port', num2str(k + 3));
    add_line(s, [sorties{k, 1} '/1'], [sorties{k, 3} '/1']);
end
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'angle des roues (rad)', [2260 683 2290 697], 'Port', '7');
add_line(s, 'Mux theta/1', 'angle des roues (rad)/1', 'autorouting', 'smart');
end

function articulation(s, nomj, pos, q0, blocage)
j = ajouter(s, 'sm_lib/Joints/Revolute Joint', nomj, pos, ...
    'JointMode', 'ProvidedByInput', 'SensePosition', 'on', 'SenseVelocity', 'on', ...
    'PositionTargetSpecify', 'on', 'PositionTargetPriority', 'High', 'PositionTargetValue', q0, 'PositionTargetValueUnits', 'deg', ...
    'VelocityTargetSpecify', 'on', 'VelocityTargetPriority', 'High', 'VelocityTargetValue', '0', 'VelocityTargetValueUnits', 'deg/s', ...
    'SpringStiffness', 'k_cables', 'SpringStiffnessUnits', 'N*m/rad', 'DampingCoefficient', 'b_cardan', 'DampingCoefficientUnits', 'N*m*s/rad', ...
    'LowerLimitSpecify', 'on', 'LowerLimitBound', '-butee_deg', 'LowerLimitBoundUnits', 'deg', ...
    'LowerLimitStiffness', 'k_butee', 'LowerLimitStiffnessUnits', 'N*m/rad', 'LowerLimitDamping', 'c_butee', 'LowerLimitDampingUnits', 'N*m*s/rad', ...
    'LowerLimitTransitionRegionWidth', '0.1', 'LowerLimitTransitionRegionWidthUnits', 'deg', ...
    'UpperLimitSpecify', 'on', 'UpperLimitBound', 'butee_deg', 'UpperLimitBoundUnits', 'deg', ...
    'UpperLimitStiffness', 'k_butee', 'UpperLimitStiffnessUnits', 'N*m/rad', 'UpperLimitDamping', 'c_butee', 'UpperLimitDampingUnits', 'N*m*s/rad', ...
    'UpperLimitTransitionRegionWidth', '0.1', 'UpperLimitTransitionRegionWidthUnits', 'deg');
set_param(j, 'Description', sprintf(['Pivot de %s : 2 roulements 625, butées à ±butee_deg (goupille dans une lumière en arc), ' ...
    'frottement b_cardan, raideur des câbles k_cables. Entrée mode : %s (0 libre, 1 bloqué par la goupille).'], lower(nomj), blocage));
c = ['Goupille ' lower(nomj)];
ajouter(s, 'simulink/Sources/Constant', c, [pos(1) - 150 pos(4) + 40 pos(1) - 90 pos(4) + 60], 'Value', blocage);
cv = ['mode ' lower(nomj)];
ajouter(s, 'nesl_utility/Simulink-PS Converter', cv, [pos(1) - 50 pos(4) + 40 pos(1) - 30 pos(4) + 60], 'Unit', '1');
add_line(s, [c '/1'], [cv '/1']);
h = get_param(j, 'PortHandles');
lier(s, get_param([s '/' cv], 'PortHandles').RConn(1), h.LConn(2));
end

function m = module_roue(s, k, angle, pos, cao)
m = sprintf('%s/Module de roue %d (%g°)', s, k, angle);
add_block('built-in/Subsystem', m, 'Position', pos);
ajouter(m, 'nesl_utility/Connection Port', 'D', [20 100 50 120], 'Side', 'Left', 'Port', '1');
ajouter(m, 'nesl_utility/Connection Port', 'Cm', [20 630 50 650], 'Side', 'Left', 'Port', '2');
ajouter(m, 'nesl_utility/Connection Port', 'omega', [760 600 790 620], 'Side', 'Right', 'Port', '3');
ajouter(m, 'nesl_utility/Connection Port', 'theta', [760 660 790 680], 'Side', 'Right', 'Port', '4');
ph = @(b) get_param([m '/' b], 'PortHandles');
poser_pieces(m, 'D', cao, sprintf('module%d', k), 30);
Rk = [cosd(angle) -sind(angle) 0; sind(angle) cosd(angle) 0; 0 0 1] * [0 0 1; 0 1 0; -1 0 0];
ajouter(m, 'sm_lib/Frames and Transforms/Rigid Transform', sprintf('Axe du moteur %d', k), [120 600 180 660], ...
    'RotationMethod', 'RotationMatrix', 'RotationMatrix', mat2str(round(Rk, 12)), 'TranslationMethod', 'None');
set_param([m sprintf('/Axe du moteur %d', k)], 'Description', ...
    sprintf('Axe Z de l''articulation = axe de l''A2212, horizontal, sur la diagonale à %g° (du centre vers l''extérieur).', angle));
lier(m, ph('D').RConn(1), ph(sprintf('Axe du moteur %d', k)).LConn(1));
j = ajouter(m, 'sm_lib/Joints/Revolute Joint', sprintf('Roue %d', k), [260 600 320 660], ...
    'TorqueActuationMode', 'InputTorque', 'SensePosition', 'on', 'SenseVelocity', 'on', ...
    'DampingCoefficient', 'f_roue', 'DampingCoefficientUnits', 'N*m*s/rad');
set_param(j, 'Description', 'Roulements de l''A2212 : couple moteur Cm en entrée ; angle et vitesse de la roue par rapport au dispositif en sortie ; frottement f_roue.');
lier(m, ph(sprintf('Axe du moteur %d', k)).RConn(1), ph(sprintf('Roue %d', k)).LConn(1));
lier(m, ph('Cm').RConn(1), ph(sprintf('Roue %d', k)).LConn(2));
lier(m, ph(sprintf('Roue %d', k)).RConn(2), ph('theta').RConn(1));
lier(m, ph(sprintf('Roue %d', k)).RConn(3), ph('omega').RConn(1));
g = groupe(m, sprintf('Rotor %d (disque, vis, rotor A2212)', k), [420 600 600 660], cao, sprintf('roue%d', k), ...
    'repère : axe du moteur (Z), origine au centre du dispositif');
lier(m, ph(sprintf('Roue %d', k)).RConn(1), get_param(g, 'PortHandles').LConn(1));
end

function g = groupe(s, nomg, pos, cao, cle, texte)
g = [s '/' nomg];
add_block('built-in/Subsystem', g, 'Position', pos);
ajouter(g, 'nesl_utility/Connection Port', 'F', [20 100 50 120], 'Side', 'Left', 'Port', '1');
poser_pieces(g, 'F', cao, cle, 40);
set_param(g, 'Description', texte);
end

function poser_pieces(g, port, cao, cle, y0)
ph = @(b) get_param([g '/' b], 'PortHandles');
I = cao.instances(strcmp({cao.instances.groupe}, cle));
n = numel(I);
for k = 1:n
    in = I(k);
    lab = strrep(in.nom, '/', ' ');
    s = cao.solides.(matlab.lang.makeValidName(in.solide));
    col = floor((k - 1) / 8); lig = mod(k - 1, 8);
    x = 120 + 560 * col; y = y0 + 65 * lig;
    fs = ajouter(g, 'sm_lib/Body Elements/File Solid', lab, [x + 260 y x + 310 y + 40], 'Orientation', 'left');
    Ig = s.I;
    rgb = sscanf(s.couleur(2:end), '%2x%2x%2x')' / 255;
    set_param(fs, 'ExtGeomFileName', s.stl, 'UnitType', 'Custom', 'ExtGeomFileUnits', 'mm', ...
        'InertiaType', 'Custom', 'Mass', num2str(s.m, 8), 'MassUnits', 'kg', ...
        'CenterOfMass', mat2str(s.G', 8), 'CenterOfMassUnits', 'm', ...
        'MomentsOfInertia', mat2str([Ig(1, 1) Ig(2, 2) Ig(3, 3)], 8), 'MomentsOfInertiaUnits', 'kg*m^2', ...
        'ProductsOfInertia', mat2str([Ig(2, 3) Ig(3, 1) Ig(1, 2)], 8), 'ProductsOfInertiaUnits', 'kg*m^2', ...
        'GraphicType', 'FromGeometry', 'GraphicVisPropType', 'SimpleVisualProperties', ...
        'GraphicDiffuseColor', mat2str(round(rgb, 3)), 'GraphicOpacity', '1');
    set_param(fs, 'Description', sprintf('Pièce CAO : %s (%s)\nMasse %.2f g : %s.\nCentre de masse et inertie : calculés sur la géométrie de la CAO.', ...
        in.nom, in.solide, s.m * 1000, s.source));
    R = in.R; t = in.t_mm(:)';
    if norm(R - eye(3)) < 1e-9 && norm(t) < 1e-9
        lier(g, ph(port).RConn(1), get_param(fs, 'PortHandles').RConn(1));
    else
        rt = ajouter(g, 'sm_lib/Frames and Transforms/Rigid Transform', ['Pose ' lab], [x y x + 50 y + 40]);
        if norm(R - eye(3)) < 1e-9
            set_param(rt, 'RotationMethod', 'None');
        else
            set_param(rt, 'RotationMethod', 'RotationMatrix', 'RotationMatrix', mat2str(round(R, 10)));
        end
        set_param(rt, 'TranslationMethod', 'Cartesian', 'TranslationCartesianOffset', mat2str(round(t, 6)), ...
            'TranslationCartesianOffsetUnits', 'mm');
        lier(g, ph(port).RConn(1), get_param(rt, 'PortHandles').LConn(1));
        lier(g, get_param(rt, 'PortHandles').RConn(1), get_param(fs, 'PortHandles').RConn(1));
    end
end
end

%% ===================================================================== outils
function b = ajouter(s, src, n, pos, varargin)
b = [s '/' strrep(n, '/', '//')];
add_block(src, b, 'Position', pos, varargin{:});
end

function lier(s, h1, h2)
add_line(s, h1, h2, 'autorouting', 'smart');
end

function journaliser(l)
set_param(get_param(l, 'SrcPortHandle'), 'DataLogging', 'on');
end

function supprimer_contenu(s)
delete_line(find_system(s, 'SearchDepth', 1, 'FindAll', 'on', 'MatchFilter', @Simulink.match.allVariants, 'Type', 'line'));
b = find_system(s, 'SearchDepth', 1, 'MatchFilter', @Simulink.match.allVariants, 'Type', 'block');
for k = 2:numel(b), delete_block(b{k}); end
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
% Bloc MATLAB Function sans entrée : exécution périodique.
ch = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', blk);
ch.ChartUpdate = 'DISCRETE';
ch.SampleTime = periode;
end

function typer_entree(blk, nom_entree, type, taille)
ch = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', blk);
d = ch.find('-isa', 'Stateflow.Data', 'Name', nom_entree);
d.DataType = type;
d.Props.Array.Size = taille;
end

function configurer_scope(b, titres)
c = get_param(b, 'ScopeConfiguration');
c.LayoutDimensions = [numel(titres) 1];
c.TimeSpan = 'auto';
c.ShowLegend = true;
for k = 1:numel(titres)
    c.ActiveDisplay = k;
    c.Title = titres{k};
    c.ShowGrid = true;
end
end

function zone(s, titre, pos, couleur)
try
    a = add_block('built-in/Area', [s '/' strrep(titre, '/', '//')], 'Position', pos);
    set_param(a, 'BackgroundColor', couleur, 'FontSize', '12', 'FontWeight', 'bold');
catch e
    fprintf('zone %s : %s\n', titre, e.message);
end
end

function note(s, xy, lignes)
persistent n
if isempty(n), n = 0; end
n = n + 1;
a = Simulink.Annotation([s sprintf('/note_%d', n)]);
a.Text = strjoin(lignes, newline);
a.Position = [xy(1) xy(2) xy(1) + 760 xy(2) + 18 * numel(lignes)];
a.FontSize = 11;
a.HorizontalAlignment = 'left';
end

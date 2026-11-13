function construire_commande_bas_niveau(fichier)
% Ajoute la commande bas niveau au modèle jumeau_banc_rw.slx, sans toucher au procédé ni au reste du modèle.
%
% Ce que le script fait :
%   - remplit le bloc « Commande bas niveau » : une boucle de vitesse par roue avec observateur CFO (4 roues) ;
%   - fait sortir du bloc « Conversion » (encore vide) une consigne en deux parties : vitesses et accélérations ;
%   - ajoute les paramètres de la commande à la fin du Model Workspace, s'ils n'y sont pas déjà ;
%   - au niveau haut, remplace les longues liaisons (retour d'état, affichage) par des Goto et From.
%
% Attention : le contenu du bloc « Commande bas niveau » est reconstruit en entier. Une modification faite à la main
% dans ce bloc serait perdue. Les réglages du Model Workspace, eux, sont conservés.

if nargin < 1
    fichier = fullfile(fileparts(fileparts(mfilename('fullpath'))), 'jumeau_banc_rw.slx');
end
[~, nom] = fileparts(fichier);
load_system(fichier);

parametres(nom);
conversion([nom '/Conversion']);
commande_bas_niveau([nom '/Commande bas niveau']);
niveau_haut(nom);
pupitre([nom '/Pupitre']);

save_system(nom, fichier);
close_system(nom, 0);
fprintf('commande bas niveau en place : %s\n', fichier);
end

%% ===================================================================== paramètres
function parametres(nom)
mws = get_param(nom, 'ModelWorkspace');
code = mws.MATLABCode;
if contains(code, 'wc_roue')
    return   % déjà en place : les réglages faits à la main sont conservés
end
ajout = {
''
'%% Commande bas niveau : une boucle de vitesse par roue, avec observateur CFO (méthode du TP2, ramenée à la vitesse)'
'J_roue = 1.562e-4;          % kg.m², inertie d''une roue autour de son axe : disque, vis, cloche du moteur (CAO)'
'T_cbn = 1/f_trame_esc;      % s, période de calcul de la commande : celle des ESC, qui ne lisent qu''une impulsion toutes les 20 ms'
'wc_roue = [10 10 10 10];    % rad/s, rapidité du suivi de vitesse de chaque roue (pôle de l''erreur en -wc)'
'wo_roue = [5 5 5 5];        % rad/s, rapidité du CFO de chaque roue (pôles en -wo et -4 wo) ; au-delà de 10, il devient instable à 20 ms'
'imp_cmd_min = 1375;         % µs, limites des impulsions commandées : vitesse conseillée des disques, 3 900 tr/min'
'imp_cmd_max = 1625;         % µs'
'w_aveugle = 45;             % rad/s, en dessous (vitesse du modèle), le TCRT5000 voit mal la roue : le CFO ne se corrige plus sur la mesure'
''
'%% Consigne d''essai des roues : ajoutée à la consigne qui vient de la conversion (0 tant qu''elle est vide)'
'essai_roue_t1 = 2;                  % s, départ vers le premier palier'
'essai_roue_vitesse1 = [0 0 0 0];    % rad/s, premier palier de chaque roue (0 : rien n''est ajouté)'
'essai_roue_t2 = 6;                  % s, départ vers le second palier'
'essai_roue_vitesse2 = [0 0 0 0];    % rad/s, second palier de chaque roue'
'essai_roue_acc = 300;               % rad/s², pente des rampes entre les paliers'
''
'%% Commande bas niveau : grandeurs calculées'
'% modèle local d''une roue : d(omega)/dt = -a1 omega + a0 V + d'
'a0_roue = Kt/(R_moteur*J_roue) * [1 1 1 1];                % rad/s² par volt'
'a1_roue = (Kt*Ke/R_moteur + f_roue)/J_roue * [1 1 1 1];    % 1/s'
'K_roue = wc_roue - a1_roue;                                % retour d''état : erreur en -(a1 + K) = -wc'
'l1_roue = 5*wo_roue;                                       % CFO'
'lambda_roue = 4/5*wo_roue;'
};
mws.MATLABCode = [code newline strjoin(ajout, newline)];
mws.reload;
end

%% ===================================================================== conversion (encore vide)
function conversion(s)
if ~isempty(find_system(s, 'SearchDepth', 1, 'Name', 'Consignes'))
    return
end
delete_line(s, 'à construire/1', 'consignes/1');
delete_block([s '/à construire']);
ajouter(s, 'simulink/Sources/Constant', 'vitesses (à construire)', [220 30 340 60], 'Value', '[0; 0; 0; 0]');
ajouter(s, 'simulink/Sources/Constant', 'accélérations (à construire)', [220 90 340 120], 'Value', '[0; 0; 0; 0]');
bc = ajouter(s, 'simulink/Signal Routing/Bus Creator', 'Consignes', [410 25 415 125], 'Inputs', '2');
set_param([s '/consignes'], 'Position', [480 68 510 82]);
relier(s, 'vitesses (à construire)/1', 'Consignes/1', 'omega_ref');
relier(s, 'accélérations (à construire)/1', 'Consignes/2', 'domega_ref');
relier(s, 'Consignes/1', 'consignes/1');
set_param(bc, 'Description', 'omega_ref : vitesse demandée à chaque roue (rad/s). domega_ref : son accélération (rad/s²).');
note(s, [30 240], {'Sortie : une consigne par roue, en deux parties. omega_ref = vitesse demandée (rad/s), domega_ref = accélération (rad/s²).', ...
    'La commande bas niveau a besoin des deux pour suivre une vitesse qui varie.'});
end

%% ===================================================================== commande bas niveau
function commande_bas_niveau(s)
vider(s);
set_param([s '/consignes des roues'], 'Position', [30 63 60 77]);
set_param([s '/état'], 'Position', [30 223 60 237]);
set_param([s '/impulsions commandées (µs)'], 'Position', [1010 653 1040 667]);

% --- consigne
ajouter(s, 'simulink/Signal Routing/Bus Selector', 'Consigne', [120 30 125 110], 'OutputSignals', 'omega_ref,domega_ref', 'ShowName', 'off');
relier(s, 'consignes des roues/1', 'Consigne/1');
e = sous_systeme(s, '+ consigne d''essai', [230 30 560 110]);
consigne_essai(e);
relier(s, 'Consigne/1', '+ consigne d''essai/1');
relier(s, 'Consigne/2', '+ consigne d''essai/2');
vers(s, '+ consigne d''essai/1', 'omega_ref', [640 38 740 62], true);
vers(s, '+ consigne d''essai/2', 'domega_ref', [640 78 740 102], true);

% --- mesure
ajouter(s, 'simulink/Signal Routing/Bus Selector', 'Vitesses des roues', [120 215 125 285], 'OutputSignals', 'vitesses_roues,roues_vues', 'ShowName', 'off');
relier(s, 'état/1', 'Vitesses des roues/1');
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture des vitesses', [300 217 350 247], 'SampleTime', 'T_cbn');
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture de la visibilité', [300 252 350 282], 'SampleTime', 'T_cbn');
relier(s, 'Vitesses des roues/1', 'Lecture des vitesses/1');
relier(s, 'Vitesses des roues/2', 'Lecture de la visibilité/1');
vers(s, 'Lecture des vitesses/1', 'omega_mes', [640 220 740 244], true);
vers(s, 'Lecture de la visibilité/1', 'capteur_voit', [640 255 740 279], true);

% --- observateur
c = sous_systeme(s, 'CFO x4', [230 400 560 520]);
cfo(c);
depuis(s, 'omega_mes', [100 408 200 432], 'CFO x4/1');
depuis(s, 'capteur_voit', [100 448 200 472], 'CFO x4/2');
depuis(s, 'V_appliquee', [100 488 200 512], 'CFO x4/3');
vers(s, 'CFO x4/1', 'omega_est', [640 418 740 442], true);
vers(s, 'CFO x4/2', 'd_est', [640 478 740 502], true);

% --- loi de commande et interface vers les ESC
l = sous_systeme(s, 'Loi de commande x4', [230 600 560 760]);
loi_commande(l);
depuis(s, 'omega_ref', [100 608 200 632], 'Loi de commande x4/1');
depuis(s, 'domega_ref', [100 648 200 672], 'Loi de commande x4/2');
depuis(s, 'omega_est', [100 688 200 712], 'Loi de commande x4/3');
depuis(s, 'd_est', [100 728 200 752], 'Loi de commande x4/4');
i = sous_systeme(s, 'Interface tension - impulsion x4', [660 640 920 720]);
interface_esc(i);
relier(s, 'Loi de commande x4/1', 'Interface tension - impulsion x4/1', 'V_commandee');
relier(s, 'Interface tension - impulsion x4/1', 'impulsions commandées (µs)/1');
vers(s, 'Interface tension - impulsion x4/2', 'V_appliquee', [1010 688 1110 712], true);

% --- affichage
ajouter(s, 'simulink/Signal Routing/Mux', 'Vitesses', [1010 150 1015 250], 'Inputs', '3', 'ShowName', 'off');
depuis(s, 'omega_ref', [880 155 970 179], 'Vitesses/1');
depuis(s, 'omega_mes', [880 188 970 212], 'Vitesses/2');
depuis(s, 'omega_est', [880 221 970 245], 'Vitesses/3');
sc = ajouter(s, 'simulink/Sinks/Scope', 'Suivi des roues', [1110 160 1160 400], 'NumInputPorts', '3');
relier(s, 'Vitesses/1', 'Suivi des roues/1');
depuis(s, 'd_est', [980 268 1070 292], 'Suivi des roues/2');
depuis(s, 'V_appliquee', [980 348 1070 372], 'Suivi des roues/3');
configurer_scope(sc, {'vitesses des roues (rad/s) : référence, mesure avec signe, estimation du CFO', ...
    'perturbation estimée par le CFO (rad/s²)', 'tension appliquée aux moteurs (V)'});

note(s, [30 810], {'Commande bas niveau : une boucle de vitesse par roue. Chaque signal porte les 4 roues ; les réglages sont des vecteurs de 4 valeurs.', ...
    'Modèle local d''une roue : d(omega)/dt = -a1 omega + a0 V + d. La perturbation d regroupe ce que le modèle ignore (frottements, ESC, écarts de paramètres).', ...
    'Vitesses des roues : la Perception leur donne leur signe (le TCRT5000 ne le donne pas) et dit si le capteur voit la roue (il la voit mal à basse vitesse).', ...
    'CFO : il estime la vitesse et la perturbation d à partir de la vitesse mesurée et de la tension appliquée. Réglage : wo_roue.', ...
    'Loi de commande : V = (-K (omega estimée - omega de référence) - d estimée + a1 omega de référence + accélération de référence) / a0. Réglage : wc_roue.', ...
    'Interface : la tension devient une impulsion d''ESC, bornée de imp_cmd_min à imp_cmd_max. Le CFO reçoit la tension réellement appliquée.', ...
    'Consigne d''essai : essai_roue_... dans le Model Workspace. Pour que la commande pilote les ESC : interrupteur « Mode » du Pupitre sur commande.'});
set_param(s, 'Description', 'Commande bas niveau : boucle de vitesse de chaque roue par placement de pôles basé sur l''observateur CFO.');
end

function consigne_essai(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'vitesse demandée (rad par s)', [30 43 60 57]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'accélération demandée (rad par s²)', [30 123 60 137]);
ajouter(s, 'simulink/Math Operations/Sum', '+ vitesse d''essai', [480 40 500 80], 'Inputs', '++', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Sum', '+ accélération d''essai', [480 120 500 160], 'Inputs', '++', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'omega de référence (rad par s)', [580 53 610 67]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'accélération de référence (rad par s²)', [580 133 610 147]);
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture de la vitesse', [150 35 200 65], 'SampleTime', 'T_cbn', 'ShowName', 'off');
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture de l''accélération', [150 115 200 145], 'SampleTime', 'T_cbn', 'ShowName', 'off');
relier(s, 'vitesse demandée (rad par s)/1', 'Lecture de la vitesse/1');
relier(s, 'accélération demandée (rad par s²)/1', 'Lecture de l''accélération/1');
relier(s, 'Lecture de la vitesse/1', '+ vitesse d''essai/1');
relier(s, 'Lecture de l''accélération/1', '+ accélération d''essai/1');
depuis(s, 'vitesse_essai', [310 58 430 82], '+ vitesse d''essai/2');
depuis(s, 'acceleration_essai', [310 138 430 162], '+ accélération d''essai/2');
relier(s, '+ vitesse d''essai/1', 'omega de référence (rad par s)/1');
relier(s, '+ accélération d''essai/1', 'accélération de référence (rad par s²)/1');

ajouter(s, 'simulink/Sources/Step', 'Palier 1', [30 255 60 285], 'Time', 'essai_roue_t1', 'Before', '[0; 0; 0; 0]', ...
    'After', 'essai_roue_vitesse1(:)', 'SampleTime', 'T_cbn');
ajouter(s, 'simulink/Sources/Step', 'Palier 2', [30 315 60 345], 'Time', 'essai_roue_t2', 'Before', '[0; 0; 0; 0]', ...
    'After', 'essai_roue_vitesse2(:) - essai_roue_vitesse1(:)', 'SampleTime', 'T_cbn');
ajouter(s, 'simulink/Math Operations/Sum', 'Paliers', [130 240 150 360], 'Inputs', '++', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Discontinuities/Rate Limiter', 'Rampe', [210 285 260 315], 'RisingSlewLimit', 'essai_roue_acc', ...
    'FallingSlewLimit', '-essai_roue_acc', 'InitialCondition', '0');
ajouter(s, 'simulink/Discrete/Discrete Derivative', 'Pente de la rampe', [390 345 460 375]);
relier(s, 'Palier 1/1', 'Paliers/1');
relier(s, 'Palier 2/1', 'Paliers/2');
relier(s, 'Paliers/1', 'Rampe/1');
vers(s, 'Rampe/1', 'vitesse_essai', [390 288 510 312]);
coude(s, 'Rampe/1', 'Pente de la rampe/1', 320);
vers(s, 'Pente de la rampe/1', 'acceleration_essai', [540 348 660 372]);
note(s, [30 430], {'Consigne d''essai, ajoutée à la consigne qui vient de la conversion : deux paliers de vitesse reliés par des rampes.', ...
    'Réglages dans le Model Workspace : essai_roue_t1, essai_roue_vitesse1, essai_roue_t2, essai_roue_vitesse2, essai_roue_acc.', ...
    'La pente de la rampe donne l''accélération de référence. Pour ne rien ajouter : mettre les deux paliers à [0 0 0 0].'});
end

function cfo(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'omega mesurée (rad par s)', [30 88 60 102]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'le capteur voit la roue (0 ou 1)', [60 188 90 202]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'V appliquée (V)', [30 343 60 357]);
ajouter(s, 'simulink/Math Operations/Sum', 'Erreur d''estimation', [150 75 170 155], 'Inputs', '+-', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Product', 'Correction si le capteur voit', [250 75 280 235], 'Inputs', '2', 'ShowName', 'off');
ajouter(s, 'simulink/Math Operations/Gain', 'l1', [350 140 410 170], 'Gain', 'l1_roue(:)');
ajouter(s, 'simulink/Math Operations/Gain', 'lambda', [470 175 530 205], 'Gain', 'lambda_roue(:)');
ajouter(s, 'simulink/Math Operations/Gain', 'Retour de z vers 0', [470 275 530 305], 'Gain', '-wo_roue(:)');
ajouter(s, 'simulink/Signal Routing/Switch', 'Le capteur voit la roue ?', [580 165 620 315], 'Criteria', 'u2 > Threshold', 'Threshold', '0.5', 'ShowName', 'off');
integrateur(s, 'z', [660 225 700 255]);
ajouter(s, 'simulink/Math Operations/Sum', 'd estimée = Le + z', [740 112 760 282], 'Inputs', '++', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Gain', 'a0', [780 335 840 365], 'Gain', 'a0_roue(:)');
ajouter(s, 'simulink/Math Operations/Gain', 'a1', [780 488 840 518], 'Gain', 'a1_roue(:)');
ajouter(s, 'simulink/Math Operations/Sum', 'Dérivée de omega estimée', [890 120 910 580], 'Inputs', '++-', 'IconShape', 'rectangular');
integrateur(s, 'omega estimée', [980 335 1020 365]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'omega estimée (rad par s)', [1140 343 1170 357]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'd estimée (rad par s²)', [1140 63 1170 77]);
% erreur d'estimation, comptée seulement si le capteur voit la roue
relier(s, 'omega mesurée (rad par s)/1', 'Erreur d''estimation/1');
depuis(s, 'omega_est', [40 123 120 147], 'Erreur d''estimation/2');
relier(s, 'Erreur d''estimation/1', 'Correction si le capteur voit/1');
relier(s, 'le capteur voit la roue (0 ou 1)/1', 'Correction si le capteur voit/2');
ajouter(s, 'simulink/Signal Routing/Goto', 'Goto voit', [235 258 295 282], 'GotoTag', 'voit', 'ShowName', 'off');
coude(s, 'le capteur voit la roue (0 ou 1)/1', 'Goto voit/1', 215);
relier(s, 'Correction si le capteur voit/1', 'l1/1');
% fonction de compensation
relier(s, 'l1/1', 'd estimée = Le + z/1', 'Le');
coude(s, 'l1/1', 'lambda/1', 440);
relier(s, 'lambda/1', 'Le capteur voit la roue ?/1');
depuis(s, 'voit', [470 228 530 252], 'Le capteur voit la roue ?/2');
relier(s, 'Retour de z vers 0/1', 'Le capteur voit la roue ?/3');
relier(s, 'Le capteur voit la roue ?/1', 'z/1');
relier(s, 'z/1', 'd estimée = Le + z/2');
add_line(s, [720 240; 720 335; 445 335; 445 290; 470 290]);   % retour de z, court : il reste autour de son intégrateur
% vitesse estimée
relier(s, 'd estimée = Le + z/1', 'Dérivée de omega estimée/1');
coude(s, 'd estimée = Le + z/1', 'd estimée (rad par s²)/1', 820);
relier(s, 'V appliquée (V)/1', 'a0/1');
relier(s, 'a0/1', 'Dérivée de omega estimée/2');
depuis(s, 'omega_est', [660 491 740 515], 'a1/1');
relier(s, 'a1/1', 'Dérivée de omega estimée/3');
relier(s, 'Dérivée de omega estimée/1', 'omega estimée/1');
relier(s, 'omega estimée/1', 'omega estimée (rad par s)/1');
ajouter(s, 'simulink/Signal Routing/Goto', 'Goto omega_est', [1090 398 1170 422], 'GotoTag', 'omega_est', 'ShowName', 'off');
coude(s, 'omega estimée/1', 'Goto omega_est/1', 1055);
note(s, [30 630], {'Observateur CFO d''une roue (celui du TP2, ramené d''un ordre : on commande une vitesse, pas une position).', ...
    'Erreur d''estimation : e = omega mesurée - omega estimée, comptée seulement quand le capteur voit la roue.          Le = l1 e.', ...
    'd(omega estimée)/dt = -a1 omega estimée + a0 V + Le + z.', ...
    'dz/dt = lambda Le quand le capteur voit la roue. Sinon dz/dt = -wo z : z revient vers 0, pour ne pas garder une valeur que rien ne corrige.', ...
    'Perturbation estimée : d estimée = Le + z.', ...
    'Gains : l1 = 5 wo, lambda = 4/5 wo. L''erreur d''estimation suit s² + (a1 + l1) s + lambda l1 : pôles en -wo et -4 wo, à a1 près.', ...
    'Les deux intégrateurs sont discrets (Euler, période T_cbn).'});
end

function loi_commande(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'omega de référence (rad par s)', [30 53 60 67]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'accélération de référence (rad par s²)', [30 133 60 147]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'omega estimée (rad par s)', [30 198 60 212]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'd estimée (rad par s²)', [30 293 60 307]);
ajouter(s, 'simulink/Math Operations/Gain', 'a1', [350 45 410 75], 'Gain', 'a1_roue(:)');
ajouter(s, 'simulink/Math Operations/Sum', 'Erreur de suivi', [230 190 250 250], 'Inputs', '+-', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Gain', 'K', [350 205 410 235], 'Gain', 'K_roue(:)');
ajouter(s, 'simulink/Math Operations/Sum', 'Somme', [520 20 540 340], 'Inputs', '++--', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Gain', '1 sur a0', [610 165 680 195], 'Gain', '1./a0_roue(:)');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'V commandée (V)', [760 173 790 187]);
relier(s, 'omega de référence (rad par s)/1', 'a1/1');
ajouter(s, 'simulink/Signal Routing/Goto', 'Goto omega_ref', [250 88 330 112], 'GotoTag', 'omega_ref', 'ShowName', 'off');
coude(s, 'omega de référence (rad par s)/1', 'Goto omega_ref/1', 220);
relier(s, 'a1/1', 'Somme/1');
relier(s, 'accélération de référence (rad par s²)/1', 'Somme/2');
relier(s, 'omega estimée (rad par s)/1', 'Erreur de suivi/1');
depuis(s, 'omega_ref', [110 223 190 247], 'Erreur de suivi/2');
relier(s, 'Erreur de suivi/1', 'K/1');
relier(s, 'K/1', 'Somme/3');
relier(s, 'd estimée (rad par s²)/1', 'Somme/4');
relier(s, 'Somme/1', '1 sur a0/1');
relier(s, '1 sur a0/1', 'V commandée (V)/1');
note(s, [30 400], {'Loi de commande d''une roue (celle du TP2, ramenée à la vitesse).', ...
    'Erreur de suivi : e = omega estimée - omega de référence. Commande virtuelle : -K e, avec K = wc - a1. L''erreur suit alors de/dt = -wc e.', ...
    'Tension : V = (-K e - d estimée + a1 omega de référence + accélération de référence) / a0.'});
end

function interface_esc(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'V commandée (V)', [30 53 60 67]);
ajouter(s, 'simulink/Math Operations/Gain', 'Volts vers µs', [120 45 190 75], 'Gain', '(imp_max - imp_neutre)/V_alim');
ajouter(s, 'simulink/Math Operations/Gain', 'Sens de rotation', [250 45 320 75], 'Gain', 'sens_moteurs(:)');
ajouter(s, 'simulink/Math Operations/Bias', '+ neutre', [380 45 440 75], 'Bias', 'imp_neutre');
ajouter(s, 'simulink/Discontinuities/Saturation', 'Limites des disques', [500 45 560 75], 'UpperLimit', 'imp_cmd_max', 'LowerLimit', 'imp_cmd_min');
ajouter(s, 'simulink/Math Operations/Rounding Function', 'Arrondi à 1 µs', [620 45 680 75], 'Operator', 'round');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'impulsions (µs)', [860 53 890 67]);
relier(s, 'V commandée (V)/1', 'Volts vers µs/1');
relier(s, 'Volts vers µs/1', 'Sens de rotation/1');
relier(s, 'Sens de rotation/1', '+ neutre/1');
relier(s, '+ neutre/1', 'Limites des disques/1');
relier(s, 'Limites des disques/1', 'Arrondi à 1 µs/1');
relier(s, 'Arrondi à 1 µs/1', 'impulsions (µs)/1');
ajouter(s, 'simulink/Signal Routing/Goto', 'Goto impulsions', [740 108 830 132], 'GotoTag', 'impulsions', 'ShowName', 'off');
coude(s, 'Arrondi à 1 µs/1', 'Goto impulsions/1', 710);
ajouter(s, 'simulink/Math Operations/Bias', '- neutre', [250 185 310 215], 'Bias', '-imp_neutre');
ajouter(s, 'simulink/Math Operations/Gain', 'Sens de rotation (retour)', [380 185 450 215], 'Gain', 'sens_moteurs(:)');
ajouter(s, 'simulink/Math Operations/Gain', 'µs vers volts', [520 185 590 215], 'Gain', 'V_alim/(imp_max - imp_neutre)');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'V appliquée (V)', [860 193 890 207]);
depuis(s, 'impulsions', [120 188 210 212], '- neutre/1');
relier(s, '- neutre/1', 'Sens de rotation (retour)/1');
relier(s, 'Sens de rotation (retour)/1', 'µs vers volts/1');
relier(s, 'µs vers volts/1', 'V appliquée (V)/1');
note(s, [30 280], {'Interface tension - impulsion : l''ESC applique V = V_alim (impulsion - neutre) / (imp_max - imp_neutre), dans le sens de rotation du moteur.', ...
    'L''impulsion est bornée de imp_cmd_min à imp_cmd_max (vitesse conseillée des disques) et arrondie à 1 µs, comme dans la trame de commande.', ...
    'Seconde sortie : la tension réellement appliquée, recalculée à partir de l''impulsion envoyée. C''est elle que le CFO doit recevoir.'});
end

%% ===================================================================== niveau haut : Goto et From
function niveau_haut(nom)
if isempty(find_system(nom, 'SearchDepth', 1, 'BlockType', 'Goto', 'GotoTag', 'etat'))
    % retour d'état
    supprimer_sortie([nom '/Perception'], 1);
    supprimer_sortie([nom '/Procédé'], 2);
    for b = {'Sel état', 'Sel réel', 'en rad par s'}
        supprimer_sortie([nom '/' b{1}], []);
        delete_block([nom '/' b{1}]);
    end
    p = get_param([nom '/Perception'], 'Position'); y = round((p(2) + p(4))/2);
    vers(nom, 'Perception/1', 'etat', [p(3) + 50 y - 12 p(3) + 110 y + 12], true);
    for b = {'Commande haut niveau', 'Commande bas niveau'}
        p = get_param([nom '/' b{1}], 'Position'); y = round(p(2) + 0.75*(p(4) - p(2)));
        depuis(nom, 'etat', [p(1) - 54 y - 12 p(1) - 8 y + 12], [b{1} '/2']);
    end
    % grandeurs réelles du jumeau
    p = get_param([nom '/Procédé'], 'Position'); y = round(p(2) + 0.75*(p(4) - p(2)));
    vers(nom, 'Procédé/2', 'grandeurs_reelles', [p(3) + 25 p(4) + 32 p(3) + 155 p(4) + 56], true);
    % affichage
    x = 2090;
    set_param([nom '/Angles (°)'], 'Position', [x + 420 160 x + 460 240]);
    set_param([nom '/Roues'], 'Position', [x + 420 290 x + 460 410]);
    ajouter(nom, 'simulink/Signal Routing/Bus Selector', 'Angles mesurés', [x + 150 165 x + 155 195], 'OutputSignals', 'angles_deg', 'ShowName', 'off');
    ajouter(nom, 'simulink/Signal Routing/Bus Selector', 'Angles réels', [x + 150 205 x + 155 235], 'OutputSignals', 'angles_cardan', 'ShowName', 'off');
    ajouter(nom, 'simulink/Signal Routing/Bus Selector', 'Vitesses mesurées', [x + 150 295 x + 155 325], 'OutputSignals', 'vitesses_roues', 'ShowName', 'off');
    ajouter(nom, 'simulink/Signal Routing/Bus Selector', 'Roues réelles', [x + 150 330 x + 155 410], 'OutputSignals', 'roues_tr_min,courants_A', 'ShowName', 'off');
    ajouter(nom, 'simulink/Math Operations/Gain', 'en rad par s', [x + 310 338 x + 370 362], 'Gain', '2*pi/60');
    depuis(nom, 'etat', [x + 60 168 x + 120 192], 'Angles mesurés/1');
    depuis(nom, 'grandeurs_reelles', [x 208 x + 120 232], 'Angles réels/1');
    depuis(nom, 'etat', [x + 60 298 x + 120 322], 'Vitesses mesurées/1');
    depuis(nom, 'grandeurs_reelles', [x 358 x + 120 382], 'Roues réelles/1');
    relier(nom, 'Angles mesurés/1', 'Angles (°)/1');
    relier(nom, 'Angles réels/1', 'Angles (°)/2');
    relier(nom, 'Vitesses mesurées/1', 'Roues/1');
    relier(nom, 'Roues réelles/1', 'en rad par s/1');
    relier(nom, 'en rad par s/1', 'Roues/2');
    relier(nom, 'Roues réelles/2', 'Roues/3');
end
% la consigne des roues est maintenant un bus : la ligne garde son nom
% texte du niveau haut
a = find_system(nom, 'FindAll', 'on', 'SearchDepth', 1, 'Type', 'annotation');
for k = 1:numel(a)
    t = get_param(a(k), 'Text');
    if contains(t, 'seul le PROCÉDÉ est rempli')
        lignes = strsplit(t, newline);
        j = find(contains(lignes, 'seul le PROCÉDÉ est rempli'), 1);
        lignes{j} = ['Remplis à cette étape : le PROCÉDÉ et la COMMANDE BAS NIVEAU (boucle de vitesse de chaque roue, avec observateur CFO). ' ...
            'Référence, commande haut niveau et conversion sont encore vides.'];
        lignes = [lignes(1:j), {'Pupitre : interrupteur « Mode » sur commande pour que la commande pilote les ESC, sur manuel pour les curseurs.'}, lignes(j + 1:end)];
        set_param(a(k), 'Text', strjoin(lignes, newline));
        p = get_param(a(k), 'Position');
        set_param(a(k), 'Position', [p(1) p(2) p(3) p(4) + 18]);
    end
end
end

function pupitre(s)
m = 'Mode : manuel (haut) ou commande (bas)'; a = 'Marche (haut) ou arrêt (bas)';
if isempty(find_system(s, 'SearchDepth', 1, 'BlockType', 'Goto', 'GotoTag', 'commande'))
    % l'entrée « commande » arrivait par une longue liaison sous les curseurs : Goto à l'entrée, From devant l'interrupteur
    supprimer_sortie([s '/commande (µs)'], 1);
    supprimer_sortie([s '/Curseurs + essai'], 1);
    supprimer_sortie([s '/' m], 1);
    supprimer_sortie([s '/Neutre'], 1);
    supprimer_sortie([s '/' a], 1);
    for b = {m, a, 'Neutre', 'imp (µs)'}
        p = get_param([s '/' b{1}], 'Position');
        set_param([s '/' b{1}], 'Position', p + [110 0 110 0]);
    end
    p = get_param([s '/commande (µs)'], 'Position'); y = round((p(2) + p(4))/2);
    vers(s, 'commande (µs)/1', 'commande', [p(3) + 90 y - 12 p(3) + 180 y + 12]);
    relier(s, 'Curseurs + essai/1', [m '/1']);
    ph = get_param([s '/' m], 'PortHandles'); c = get_param(ph.Inport(2), 'Position');
    depuis(s, 'commande', [c(1) - 130 c(2) - 12 c(1) - 40 c(2) + 12], [m '/2']);
    relier(s, [m '/1'], [a '/1']);
    relier(s, 'Neutre/1', [a '/2']);
    relier(s, [a '/1'], 'imp (µs)/1');
end
set_param([s '/' m], 'sw', '0');   % la commande pilote les ESC
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

function coude(s, src, dst, x)
% Liaison en équerre : part de la sortie src (ou de sa liaison si elle existe déjà), tourne à l'abscisse x, arrive sur dst.
c = strsplit(src, '/'); ph = get_param([s '/' strjoin(c(1:end - 1), '/')], 'PortHandles'); ps = ph.Outport(str2double(c{end}));
c = strsplit(dst, '/'); ph = get_param([s '/' strjoin(c(1:end - 1), '/')], 'PortHandles'); pd = ph.Inport(str2double(c{end}));
a = get_param(ps, 'Position'); b = get_param(pd, 'Position');
pts = [x a(2); x b(2); b];
if get_param(ps, 'Line') == -1, pts = [a; pts]; end
l = add_line(s, pts);
if get_param(pd, 'Line') == -1 || get_param(get_param(pd, 'Line'), 'SrcPortHandle') ~= ps
    delete_line(l);
    add_line(s, src, dst, 'autorouting', 'smart');
    fprintf('liaison en équerre refaite automatiquement : %s -> %s\n', src, dst);
end
end

function integrateur(s, n, pos)
ajouter(s, 'simulink/Discrete/Discrete-Time Integrator', n, pos, 'IntegratorMethod', 'Integration: Forward Euler', ...
    'gainval', '1', 'InitialCondition', '0', 'SampleTime', 'T_cbn');
end

function l = relier(s, src, dst, nomsignal)
l = add_line(s, src, dst, 'autorouting', 'smart');
if nargin > 3, set_param(l, 'Name', nomsignal); end
end

function vers(s, src, etiquette, pos, enregistrer)
% Goto : le signal porte le nom de l'étiquette. enregistrer = true : il est aussi enregistré pendant la simulation.
n = nom_libre(s, ['Goto ' etiquette]);
ajouter(s, 'simulink/Signal Routing/Goto', n, pos, 'GotoTag', etiquette, 'ShowName', 'off');
l = add_line(s, src, [n '/1'], 'autorouting', 'smart');
ph = get_param(l, 'SrcPortHandle');
if isempty(get_param(ph, 'Name')), set_param(ph, 'Name', etiquette); end
if nargin > 4 && enregistrer, set_param(ph, 'DataLogging', 'on'); end
end

function depuis(s, etiquette, pos, dst)
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

function journaliser(s, sortie)
c = strsplit(sortie, '/');
ph = get_param([s '/' c{1}], 'PortHandles');
set_param(ph.Outport(str2double(c{2})), 'DataLogging', 'on');
end

function supprimer_sortie(blk, ports)
ph = get_param(blk, 'PortHandles');
if isempty(ports), ports = 1:numel(ph.Outport); end
for k = ports
    l = get_param(ph.Outport(k), 'Line');
    if l ~= -1, delete_line(l); end
end
end

function vider(s)
% Efface le contenu d'un sous-système en gardant ses ports : les liaisons du niveau au-dessus restent en place.
delete_line(find_system(s, 'SearchDepth', 1, 'FindAll', 'on', 'Type', 'line'));
b = find_system(s, 'SearchDepth', 1, 'Type', 'block');
for k = 2:numel(b)
    if ~any(strcmp(get_param(b{k}, 'BlockType'), {'Inport', 'Outport'})), delete_block(b{k}); end
end
delete(find_system(s, 'SearchDepth', 1, 'FindAll', 'on', 'Type', 'annotation'));
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

function note(s, xy, lignes)
a = Simulink.Annotation(s, strjoin(lignes, newline));
a.Position = [xy(1) xy(2) xy(1) + 900 xy(2) + 18 * numel(lignes)];
a.FontSize = 11;
a.HorizontalAlignment = 'left';
end

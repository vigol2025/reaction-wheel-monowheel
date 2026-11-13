function construire_commande_haut_niveau(fichier)
% Complète la commande du modèle jumeau_banc_rw.slx : référence, commande haut niveau, conversion.
% La commande bas niveau doit déjà être en place (construire_commande_bas_niveau.m). La commande haut niveau lit l'état
% donné par la Perception (construire_perception.m) ; la référence lit le manche de l'interface (construire_pilotage.m).
%
% Ce que le script fait :
%   - remplit « Référence » : angles demandés, programmés en polynômes de degré 5, ou donnés par le manche de l'interface ;
%   - remplit « Commande haut niveau » : une boucle par axe, placement de pôles basé sur l'observateur CFO (TP2) ;
%   - remplit « Conversion » : couples des deux axes vers vitesse et accélération de chaque roue ;
%   - ajoute au jumeau Simscape la tenue à la main au départ (t_lacher) et une poussée d'essai (couple sur les axes) ;
%   - ajoute les paramètres au Model Workspace, s'ils n'y sont pas déjà.
%
% Attention : le contenu des blocs Référence, Commande haut niveau et Conversion est reconstruit en entier. Une
% modification faite à la main dans ces blocs serait perdue. Les réglages du Model Workspace sont conservés.

if nargin < 1
    fichier = fullfile(fileparts(fileparts(mfilename('fullpath'))), 'jumeau_banc_rw.slx');
end
[~, nom] = fileparts(fichier);
load_system(fichier);

parametres(nom);
reference([nom '/Référence']);
conversion([nom '/Conversion']);
commande_haut_niveau([nom '/Commande haut niveau']);
commande_bas_niveau([nom '/Commande bas niveau']);
procede_simscape([nom '/Procédé/Jumeau Simscape/Mécanique (CAO version 3)']);
niveau_haut(nom);

save_system(nom, fichier);
close_system(nom, 0);
fprintf('commande complète en place : %s\n', fichier);
end

%% ===================================================================== paramètres
function parametres(nom)
mws = get_param(nom, 'ModelWorkspace');
code = mws.MATLABCode;
if ~contains(code, 't_lacher')
    essai = {
    '%% Essai : maintien au départ et perturbation'
    't_lacher = 2;                % s, le dispositif est tenu à la main à sa position de départ jusqu''à cet instant (0 : libre dès le départ)'
    'k_main = 5;                  % N.m/rad, raideur de la main qui tient le dispositif'
    'c_main = 0.3;                % N.m.s/rad, son amortissement'
    'perturbation_t = 7;          % s, instant de la poussée d''essai'
    'perturbation_duree = 0.2;    % s'
    'perturbation_couple = [0.02 0.02];   % N.m, couple de la poussée sur [roulis tangage] (0 : aucune)'
    ''
    '%% Grandeurs dérivées'};
    assert(contains(code, '%% Grandeurs dérivées'));
    code = strrep(code, '%% Grandeurs dérivées', strjoin(essai, newline));
    a = 'R_montage_bno(:); T_pont];   % 48 valeurs envoyées au jumeau Webots au lancement';
    assert(contains(code, a));
    code = strrep(code, a, ['R_montage_bno(:); T_pont; t_lacher; k_main; c_main; perturbation_t; perturbation_duree; perturbation_couple(:)];' ...
        '   % 55 valeurs envoyées au jumeau Webots au lancement']);
    % la consigne d'essai des roues ne sert plus par défaut : la commande haut niveau donne la consigne ;
    % et le dispositif doit être libre pour que la commande ait quelque chose à stabiliser
    code = regexprep(code, '(?m)^blocage_roulis = [^;]*;', 'blocage_roulis = 0;');
    code = regexprep(code, '(?m)^blocage_tangage = [^;]*;', 'blocage_tangage = 0;');
    code = regexprep(code, '(?m)^essai_roue_vitesse1 = [^;]*;', 'essai_roue_vitesse1 = [0 0 0 0];');
end
if ~contains(code, 'wc_axe')
    ajout = {
    ''
    '%% Référence : angles demandés au dispositif, en polynômes de degré 5 entre deux paliers'
    'ref_t = [2 12];              % s, instant de départ vers chaque palier'
    'ref_roulis_deg = [0 5];      % °, roulis demandé à chaque palier'
    'ref_tangage_deg = [0 0];     % °, tangage demandé à chaque palier'
    'ref_duree = 1.5;             % s, durée du passage d''un palier au suivant'
    ''
    '%% Commande haut niveau : une boucle par axe [roulis tangage], placement de pôles basé sur l''observateur CFO (TP2)'
    'T_chn = T_cbn;               % s, période de calcul : celle de la commande bas niveau et des ESC'
    't_depart = t_lacher;         % s, mise en marche de la commande : au moment où la main lâche le dispositif'
    'wc_axe = [4 4];              % rad/s, rapidité du suivi d''angle de chaque axe'
    'xi_axe = [1 1];              % amortissement'
    'wo_axe = [3 3];              % rad/s, rapidité du CFO de chaque axe (pôles en -wo et -4 wo, double) ; au-delà de 4, le couple s''agite'
    'desat_active = 1;            % 1 : la référence est décalée pour ramener les roues vers leur vitesse de repos'
    'T_desat = 5;                 % s, constante de temps de ce retour'
    'desat_max_deg = 15;          % °, décalage maximal de la référence'
    ''
    '%% Conversion : couples des deux axes vers les 4 roues'
    'w_repos = 200;               % rad/s, vitesse de repos des 4 roues : elles tournent toujours, le TCRT5000 les voit toujours'
    't_roues = t_armement + 0.2;  % s, mise en rotation des roues, une fois les ESC armés'
    'acc_roue_max = 300;          % rad/s², accélération maximale demandée à une roue'
    'w_roue_min = 60;             % rad/s, vitesses limites demandées à une roue'
    'w_roue_max = 400;            % rad/s (disques : 3 900 tr/min conseillés, soit 408 rad/s)'
    ''
    '%% Masses et inerties utilisées par la commande (CAO du banc version 3)'
    'm_disp = 1.1870;             % kg, dispositif et ses 4 roues'
    'zG_disp = 27.836e-3;         % m, hauteur de son centre de masse sur le corps (le pivot est à pivot_mm)'
    'Ixx_disp_24 = 7.7608e-3;     % kg.m², inertie du dispositif autour du roulis, pivot à +24 mm'
    'Iyy_disp_24 = 7.7554e-3;     % kg.m², autour du tangage, pivot à +24 mm'
    'm_croix = 0.0755;            % kg, croisillon et paliers (ne tournent qu''en roulis)'
    'zG_croix = 0.257e-3;         % m, hauteur de leur centre de masse au-dessus de l''axe de roulis'
    'Ixx_croix = 2.073e-4;        % kg.m²'
    ''
    '%% Commande haut niveau et conversion : grandeurs calculées'
    '% modèle local d''un axe : d²(theta)/dt² = -a1 d(theta)/dt + a0 C + d, avec C le couple demandé aux roues'
    'hz = zG_disp - pivot_mm/1000;                                    % m, centre de masse du dispositif au-dessus du pivot'
    'I_axe = [Ixx_disp_24 + Ixx_croix, Iyy_disp_24] + m_disp*(hz^2 - (zG_disp - 0.024)^2) - 2*J_roue;   % kg.m²'
    'mgh_axe = g*[m_disp*hz + m_croix*zG_croix, m_disp*hz];           % N.m/rad, couple de pesanteur par radian d''inclinaison'
    'a0_axe = 1./I_axe;                                               % rad/s² par N.m'
    'a1_axe = b_cardan./I_axe;                                        % 1/s'
    'k1_axe = wc_axe.^2;                                              % retour d''état : s² + 2 xi wc s + wc²'
    'k2_axe = 2*xi_axe.*wc_axe - a1_axe;'
    'l1_axe = 9*wo_axe;                                               % CFO du TP2'
    'l2_axe = 12*wo_axe.^2;'
    'lambda_axe = 4/3*wo_axe;'
    'C_max = 2*J_roue*cosd(45)*acc_roue_max;                          % N.m, couple maximal demandé sur un axe'
    'k_desat = desat_active./(max(mgh_axe, 1e-3)*T_desat);            % rad par N.m.s'
    'sx_roues = [1 -1 -1 1];                                          % signe de cos(45°, 135°, 225°, 315°) : part de chaque roue sur le roulis'
    'sy_roues = [1 1 -1 -1];                                          % signe de sin : part sur le tangage'
    'M_conv = -[sx_roues(:) sy_roues(:)]/(4*J_roue*cosd(45));         % accélération des 4 roues pour un couple [roulis; tangage]'
    };
    code = [code newline strjoin(ajout, newline)];
end
if ~contains(code, 'manche_max_deg')
    manche = {
    ''
    '%% Pilotage par l''interface (pilotage/pilote_banc.m)'
    'manche_max_deg = 15;         % °, limite de sécurité de l''inclinaison demandée par le manche (l''interface règle l''amplitude)'
    'w_manche = 3;                % rad/s, rapidité avec laquelle la référence rejoint le manche (second ordre critique)'
    'T_affichage = 0.1;           % s, rafraîchissement de l''interface'
    };
    code = [code newline strjoin(manche, newline)];
end
mws.MATLABCode = code;
mws.reload;
end

%% ===================================================================== référence
function reference(s)
vider(s);
if isempty(find_system(s, 'SearchDepth', 1, 'BlockType', 'Inport', 'Name', 'manche'))
    add_block('simulink/Ports & Subsystems/In1', [s '/manche']);
end
set_param([s '/manche'], 'Position', [30 263 60 277]);
set_param([s '/consigne (°)'], 'Position', [860 143 890 157]);
ajouter(s, 'simulink/Sources/Digital Clock', 'Temps', [30 68 90 92], 'SampleTime', 'T_chn');
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Programme : polynômes de degré 5', [170 20 350 140]);
script_fonction(fn, {
'function [angle, vitesse, acceleration] = polynomes(t, ref_t, ref_roulis_deg, ref_tangage_deg, ref_duree, q0_deg)'
'% Référence programmée de roulis et de tangage. À chaque instant ref_t(i), le dispositif part vers le palier i'
'% [ref_roulis_deg(i) ; ref_tangage_deg(i)] et y arrive ref_duree plus tard, par un polynôme de degré 5 :'
'% vitesse et accélération nulles au départ et à l''arrivée. Avant ref_t(1) : la position de départ q0_deg.'
'% Sorties en degrés, degrés par seconde et degrés par seconde carrée, [roulis ; tangage].'
'cibles = [ref_roulis_deg(:) ref_tangage_deg(:)];'
'angle = q0_deg(:); vitesse = zeros(2, 1); acceleration = zeros(2, 1);'
'for i = 1:numel(ref_t)'
'    if t >= ref_t(i)'
'        if i == 1, a = q0_deg(:); else, a = cibles(i - 1, :).''; end'
'        b = cibles(i, :).'';'
'        s = min((t - ref_t(i)) / ref_duree, 1);'
'        angle = a + (b - a) * (10*s^3 - 15*s^4 + 6*s^5);'
'        vitesse = (b - a) * (30*s^2 - 60*s^3 + 30*s^4) / ref_duree;'
'        acceleration = (b - a) * (60*s - 180*s^2 + 120*s^3) / ref_duree^2;'
'    end'
'end'
}, {'ref_t', 'ref_roulis_deg', 'ref_tangage_deg', 'ref_duree', 'q0_deg'});
relier(s, 'Temps/1', 'Programme : polynômes de degré 5/1');
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Manche : filtre du second ordre', [170 220 350 340]);
script_fonction(fn, {
'function [angle, vitesse, acceleration, actif] = filtre(manche, angle_programme, t, T_chn, w_manche, manche_max_deg, t_depart)'
'% Référence donnée par le manche de l''interface de pilotage. manche = [actif ; roulis demandé ; tangage demandé] (°).'
'% L''angle demandé, borné à manche_max_deg, est suivi par un second ordre critique de pulsation w_manche :'
'% d²(angle)/dt² = w_manche² (demandé - angle) - 2 w_manche d(angle)/dt. On en tire la vitesse et l''accélération que la'
'% loi de commande du TP2 demande. Manche inactif, ou dispositif encore tenu (avant t_depart) : le filtre suit la référence'
'% programmée, sans à-coup au passage au manche.'
'persistent x v'
'if isempty(x), x = angle_programme(:); v = zeros(2, 1); end'
'actif = double(manche(1) > 0.5 && t >= t_depart);'
'if actif'
'    c = max(-manche_max_deg, min(manche_max_deg, manche(2:3)));'
'    a = w_manche^2 * (c(:) - x) - 2 * w_manche * v;'
'else'
'    x = angle_programme(:); v = zeros(2, 1); a = zeros(2, 1);'
'end'
'angle = x; vitesse = v; acceleration = a;'
'x = x + T_chn * v;'
'v = v + T_chn * a;'
}, {'T_chn', 'w_manche', 'manche_max_deg', 't_depart'});
relier(s, 'manche/1', 'Manche : filtre du second ordre/1');
coude(s, 'Programme : polynômes de degré 5/1', 'Manche : filtre du second ordre/2', 400);
coude(s, 'Temps/1', 'Manche : filtre du second ordre/3', 120);
n = {'angle', 'vitesse', 'accélération'};
for k = 1:3
    y = 40 + 50 * (k - 1);
    ajouter(s, 'simulink/Signal Routing/Switch', ['Choix : ' n{k}], [560 y 600 y + 40], 'Criteria', 'u2 > Threshold', 'Threshold', '0.5', 'ShowName', 'off');
    depuis(s, 'manche_actif', [460 y + 10 540 y + 30], sprintf('Choix : %s/2', n{k}));
end
vers(s, 'Manche : filtre du second ordre/4', 'manche_actif', [440 318 520 342], true);
for k = 1:3
    relier(s, sprintf('Manche : filtre du second ordre/%d', k), sprintf('Choix : %s/1', n{k}));
    relier(s, sprintf('Programme : polynômes de degré 5/%d', k), sprintf('Choix : %s/3', n{k}));
end
bc = ajouter(s, 'simulink/Signal Routing/Bus Creator', 'Consigne', [720 90 725 210], 'Inputs', '3', 'ShowName', 'off');
relier(s, 'Choix : angle/1', 'Consigne/1', 'angles_ref_deg');
relier(s, 'Choix : vitesse/1', 'Consigne/2', 'vitesses_ref_dps');
relier(s, 'Choix : accélération/1', 'Consigne/3', 'accelerations_ref_dps2');
relier(s, 'Consigne/1', 'consigne (°)/1');
set_param(bc, 'Description', 'angles_ref_deg (°), vitesses_ref_dps (°/s), accelerations_ref_dps2 (°/s²), [roulis ; tangage].');
note(s, [30 400], {'Référence : angles de roulis et de tangage demandés au dispositif, avec leur vitesse et leur accélération.', ...
    'Programme : à chaque instant ref_t(i), départ vers le palier [ref_roulis_deg(i) ; ref_tangage_deg(i)], atteint en ref_duree par un polynôme de degré 5.', ...
    'Manche : quand l''interface de pilotage (pilotage/pilote_banc.m) est ouverte, l''angle vient du manche, suivi par un second ordre critique (w_manche).', ...
    'Réglages dans le Model Workspace : ref_t, ref_roulis_deg, ref_tangage_deg, ref_duree, w_manche, manche_max_deg.'});
set_param(s, 'Description', 'Référence : angles demandés au dispositif, programmés ou donnés par le manche de l''interface de pilotage.');
end

%% ===================================================================== conversion
function conversion(s)
vider(s);
set_param([s '/couples (N.m)'], 'Position', [30 73 60 87]);
set_param([s '/consignes'], 'Position', [760 443 790 457]);
% couples des axes vers accélération des roues
ajouter(s, 'simulink/Math Operations/Gain', 'Répartition sur les 4 roues', [140 62 260 98], 'Gain', 'M_conv', 'Multiplication', 'Matrix(K*u)');
ajouter(s, 'simulink/Discontinuities/Saturation', 'Accélération maximale', [340 65 400 95], 'UpperLimit', 'acc_roue_max', 'LowerLimit', '-acc_roue_max');
relier(s, 'couples (N.m)/1', 'Répartition sur les 4 roues/1');
relier(s, 'Répartition sur les 4 roues/1', 'Accélération maximale/1');
vers(s, 'Accélération maximale/1', 'acceleration', [480 68 580 92]);
% accélération vers écart de vitesse
ajouter(s, 'simulink/Discrete/Discrete-Time Integrator', 'Écart à la vitesse de repos', [340 165 400 195], ...
    'IntegratorMethod', 'Integration: Forward Euler', 'gainval', '1', 'InitialCondition', '0', 'SampleTime', 'T_chn', ...
    'LimitOutput', 'on', 'UpperSaturationLimit', 'max(w_roue_max - w_repos, 0)', 'LowerSaturationLimit', 'min(w_roue_min - w_repos, 0)');
depuis(s, 'acceleration', [140 168 240 192], 'Écart à la vitesse de repos/1');
vers(s, 'Écart à la vitesse de repos/1', 'ecart_vitesse', [480 168 580 192]);
% mise en rotation des roues
ajouter(s, 'simulink/Sources/Step', 'Mise en rotation', [140 265 170 295], 'Time', 't_roues', 'Before', '[0; 0; 0; 0]', ...
    'After', 'w_repos*[1; 1; 1; 1]', 'SampleTime', 'T_chn');
ajouter(s, 'simulink/Discontinuities/Rate Limiter', 'Rampe', [250 265 300 295], 'RisingSlewLimit', 'acc_roue_max', ...
    'FallingSlewLimit', '-acc_roue_max', 'InitialCondition', '0');
ajouter(s, 'simulink/Discrete/Discrete Derivative', 'Pente de la rampe', [400 325 470 355]);
relier(s, 'Mise en rotation/1', 'Rampe/1');
vers(s, 'Rampe/1', 'vitesse_repos', [480 268 580 292]);
coude(s, 'Rampe/1', 'Pente de la rampe/1', 350);
vers(s, 'Pente de la rampe/1', 'acceleration_repos', [540 328 660 352]);
% consignes des roues
ajouter(s, 'simulink/Math Operations/Sum', 'Vitesse demandée', [340 400 360 460], 'Inputs', '++', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Sum', 'Accélération demandée', [340 490 360 550], 'Inputs', '++', 'IconShape', 'rectangular');
depuis(s, 'ecart_vitesse', [140 403 260 427], 'Vitesse demandée/1');
depuis(s, 'vitesse_repos', [140 433 260 457], 'Vitesse demandée/2');
depuis(s, 'acceleration', [140 493 260 517], 'Accélération demandée/1');
depuis(s, 'acceleration_repos', [140 523 260 547], 'Accélération demandée/2');
bc = ajouter(s, 'simulink/Signal Routing/Bus Creator', 'Consignes', [640 400 645 500], 'Inputs', '2', 'ShowName', 'off');
relier(s, 'Vitesse demandée/1', 'Consignes/1', 'omega_ref');
relier(s, 'Accélération demandée/1', 'Consignes/2', 'domega_ref');
relier(s, 'Consignes/1', 'consignes/1');
set_param(bc, 'Description', 'omega_ref : vitesse demandée à chaque roue (rad/s). domega_ref : son accélération (rad/s²).');
note(s, [30 610], {'Conversion : couples demandés sur les deux axes vers la vitesse et l''accélération de chaque roue.', ...
    'Une roue qui accélère pousse le dispositif en sens inverse : accélération des 4 roues = M_conv [couple de roulis ; couple de tangage].', ...
    'Les roues sont à 45°, 135°, 225° et 315° : chacune agit sur les deux axes, à part égale (cos 45°).', ...
    'L''accélération s''ajoute à la vitesse de repos w_repos, la même pour les 4 roues : deux roues opposées tournent alors en sens contraire', ...
    'et leurs effets s''annulent. Les roues ne passent jamais par l''arrêt, où le TCRT5000 ne les voit plus.', ...
    'Limites : acc_roue_max sur l''accélération, w_roue_min et w_roue_max sur la vitesse demandée.'});
set_param(s, 'Description', 'Conversion : couples des deux axes vers vitesse et accélération de chaque roue.');
end

%% ===================================================================== commande haut niveau
function commande_haut_niveau(s)
vider(s);
set_param([s '/consigne (°)'], 'Position', [30 80 60 94]);
set_param([s '/état'], 'Position', [30 263 60 277]);
set_param([s '/couples des axes (N.m)'], 'Position', [1050 733 1080 747]);

% --- référence, décalée par la désaturation
ajouter(s, 'simulink/Signal Routing/Bus Selector', 'Consigne', [120 20 125 155], 'OutputSignals', ...
    'angles_ref_deg,vitesses_ref_dps,accelerations_ref_dps2', 'ShowName', 'off');
relier(s, 'consigne (°)/1', 'Consigne/1');
r = sous_systeme(s, 'Référence et désaturation x2', [280 20 610 200]);
reference_desaturation(r);
relier(s, 'Consigne/1', 'Référence et désaturation x2/1');
relier(s, 'Consigne/2', 'Référence et désaturation x2/2');
relier(s, 'Consigne/3', 'Référence et désaturation x2/3');
depuis(s, 'moment_roues', [150 165 250 189], 'Référence et désaturation x2/4');
vers(s, 'Référence et désaturation x2/1', 'theta_ref', [690 38 790 62], true);
vers(s, 'Référence et désaturation x2/2', 'dtheta_ref', [690 98 790 122]);
vers(s, 'Référence et désaturation x2/3', 'ddtheta_ref', [690 158 790 182]);

% --- mesures
ajouter(s, 'simulink/Signal Routing/Bus Selector', 'État mesuré', [120 240 125 330], 'OutputSignals', 'angles,vitesses,moment_roues', 'ShowName', 'off');
relier(s, 'état/1', 'État mesuré/1');
m = sous_systeme(s, 'Mesures x2', [280 240 610 300]);
mesures(m);
relier(s, 'État mesuré/1', 'Mesures x2/1');
relier(s, 'État mesuré/2', 'Mesures x2/2');
vers(s, 'État mesuré/3', 'moment_roues', [690 303 790 327]);
vers(s, 'Mesures x2/1', 'theta_mes', [690 243 790 267], true);
vers(s, 'Mesures x2/2', 'dtheta_mes', [690 273 790 297], true);

% --- observateur
c = sous_systeme(s, 'CFO x2', [280 380 610 500]);
cfo(c);
depuis(s, 'theta_mes', [150 388 250 412], 'CFO x2/1');
depuis(s, 'dtheta_mes', [150 428 250 452], 'CFO x2/2');
depuis(s, 'C_applique', [150 468 250 492], 'CFO x2/3');
vers(s, 'CFO x2/1', 'theta_est', [690 388 790 412], true);
vers(s, 'CFO x2/2', 'dtheta_est', [690 428 790 452], true);
vers(s, 'CFO x2/3', 'd_axe_est', [690 468 790 492], true);

% --- loi de commande, limite et mise en marche
l = sous_systeme(s, 'Loi de commande x2', [280 590 610 890]);
loi_commande(l);
n = {'theta_ref', 'dtheta_ref', 'ddtheta_ref', 'theta_est', 'dtheta_est', 'd_axe_est'};
for k = 1:6
    depuis(s, n{k}, [150 603 + 50*(k - 1) 250 627 + 50*(k - 1)], sprintf('Loi de commande x2/%d', k));
end
g = sous_systeme(s, 'Limite et mise en marche x2', [720 710 940 770]);
limite(g);
relier(s, 'Loi de commande x2/1', 'Limite et mise en marche x2/1', 'C_calcule');
relier(s, 'Limite et mise en marche x2/1', 'couples des axes (N.m)/1');
ajouter(s, 'simulink/Signal Routing/Goto', 'Goto C_applique', [1050 788 1150 812], 'GotoTag', 'C_applique', 'ShowName', 'off');
coude(s, 'Limite et mise en marche x2/1', 'Goto C_applique/1', 1000);
ph = get_param([s '/Limite et mise en marche x2'], 'PortHandles');
set_param(ph.Outport(1), 'Name', 'C_applique', 'DataLogging', 'on');

% --- affichage
ajouter(s, 'simulink/Signal Routing/Mux', 'Angles', [1010 150 1015 250], 'Inputs', '3', 'ShowName', 'off');
depuis(s, 'theta_ref', [880 155 970 179], 'Angles/1');
depuis(s, 'theta_mes', [880 188 970 212], 'Angles/2');
depuis(s, 'theta_est', [880 221 970 245], 'Angles/3');
ajouter(s, 'simulink/Math Operations/Gain', 'en degrés', [1050 185 1100 215], 'Gain', '180/pi');
relier(s, 'Angles/1', 'en degrés/1');
sc = ajouter(s, 'simulink/Sinks/Scope', 'Suivi des axes', [1170 160 1220 400], 'NumInputPorts', '3');
relier(s, 'en degrés/1', 'Suivi des axes/1');
depuis(s, 'd_axe_est', [1040 268 1130 292], 'Suivi des axes/2');
depuis(s, 'C_applique', [1040 348 1130 372], 'Suivi des axes/3');
configurer_scope(sc, {'angles du dispositif (°) : référence, mesure du BNO055, estimation du CFO', ...
    'perturbation estimée par le CFO (rad/s²)', 'couples demandés aux roues (N.m)'});

note(s, [30 940], {'Commande haut niveau : une boucle par axe. Chaque signal porte les 2 axes [roulis ; tangage] ; les réglages sont des vecteurs de 2 valeurs.', ...
    'Modèle local d''un axe : d²(theta)/dt² = -a1 d(theta)/dt + a0 C + d, avec C le couple demandé aux roues. La perturbation d regroupe la pesanteur,', ...
    'le décalage du centre de masse, les couplages entre axes et les poussées.', ...
    'CFO (TP2) : il estime l''angle, la vitesse et la perturbation d à partir de l''angle et de la vitesse donnés par la Perception et du couple demandé. Réglage : wo_axe.', ...
    'Loi de commande (TP2) : C = (-K e - d estimée + a1 vitesse de référence + accélération de référence) / a0. Réglages : wc_axe, xi_axe.', ...
    'Désaturation : la référence est décalée pour que la pesanteur ramène les roues à leur vitesse de repos. Réglages : desat_active, T_desat.', ...
    'La commande démarre à t_depart, quand la main lâche le dispositif. Le couple est borné à C_max.'});
set_param(s, 'Description', 'Commande haut niveau : stabilisation de l''inclinaison par placement de pôles basé sur l''observateur CFO, une boucle par axe.');
end

function reference_desaturation(s)
n = {'angle demandé (°)', 'vitesse demandée (° par s)', 'accélération demandée (° par s²)'};
o = {'theta de référence (rad)', 'vitesse de référence (rad par s)', 'accélération de référence (rad par s²)'};
for k = 1:3
    y = 60 + 80*(k - 1);
    ajouter(s, 'simulink/Ports & Subsystems/In1', n{k}, [30 y - 7 60 y + 7]);
    ajouter(s, 'simulink/Math Operations/Gain', sprintf('en radians %d', k), [280 y - 15 340 y + 15], 'Gain', 'pi/180', 'ShowName', 'off');
    relier(s, [n{k} '/1'], sprintf('en radians %d/1', k));
end
ajouter(s, 'simulink/Ports & Subsystems/In1', 'moment cinétique des roues (N.m.s)', [30 333 60 347]);
ajouter(s, 'simulink/Math Operations/Sum', 'Référence décalée', [560 45 580 105], 'Inputs', '+-', 'IconShape', 'rectangular');
relier(s, 'en radians 1/1', 'Référence décalée/1');
depuis(s, 'decalage', [430 78 520 102], 'Référence décalée/2');
ajouter(s, 'simulink/Ports & Subsystems/Out1', o{1}, [680 68 710 82]);
relier(s, 'Référence décalée/1', [o{1} '/1']);
for k = 2:3
    y = 60 + 80*(k - 1);
    ajouter(s, 'simulink/Ports & Subsystems/Out1', o{k}, [680 y - 7 710 y + 7]);
    relier(s, sprintf('en radians %d/1', k), [o{k} '/1']);
end
% moment cinétique confié aux roues, puis décalage de la référence
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture du moment', [150 325 200 355], 'SampleTime', 'T_chn');
ajouter(s, 'simulink/Math Operations/Gain', 'k_desat', [290 325 350 355], 'Gain', 'k_desat(:)');
ajouter(s, 'simulink/Discontinuities/Saturation', 'Décalage maximal', [420 325 480 355], 'UpperLimit', 'desat_max_deg*pi/180', 'LowerLimit', '-desat_max_deg*pi/180');
relier(s, 'moment cinétique des roues (N.m.s)/1', 'Lecture du moment/1');
relier(s, 'Lecture du moment/1', 'k_desat/1');
relier(s, 'k_desat/1', 'Décalage maximal/1');
vers(s, 'Décalage maximal/1', 'decalage', [560 328 650 352]);
note(s, [30 420], {'La référence arrive en degrés et repart en radians.', ...
    'Désaturation. Un couple constant sur un axe oblige les roues à accélérer sans fin. Le moment cinétique des roues est mesuré par la', ...
    'Perception (vitesses des roues avec leur signe). La référence d''angle est décalée de k_desat fois ce moment : le dispositif se penche un peu, et la', ...
    'pesanteur rend aux roues leur vitesse de repos avec la constante de temps T_desat. À la fin, le dispositif est à son point d''équilibre.', ...
    'desat_active = 0 : pas de décalage. C''est le réglage du banc équilibré : il n''a plus de point d''équilibre imposé, et se pencher ne', ...
    'décharge plus les roues.'});
end

function mesures(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'angles (rad)', [30 53 60 67]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'vitesses (rad par s)', [30 143 60 157]);
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture des angles', [150 45 200 75], 'SampleTime', 'T_chn');
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture des vitesses', [150 135 200 165], 'SampleTime', 'T_chn');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'theta mesurée (rad)', [300 53 330 67]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'omega mesurée (rad par s)', [300 143 330 157]);
relier(s, 'angles (rad)/1', 'Lecture des angles/1');
relier(s, 'Lecture des angles/1', 'theta mesurée (rad)/1');
relier(s, 'vitesses (rad par s)/1', 'Lecture des vitesses/1');
relier(s, 'Lecture des vitesses/1', 'omega mesurée (rad par s)/1');
note(s, [30 230], {'Angles et vitesses de roulis et de tangage, donnés par la Perception (quaternion et gyroscope du BNO055, ramenés aux axes', ...
    'du cardan), lus à chaque période de la commande.'});
end

function cfo(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'theta mesurée (rad)', [30 53 60 67]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'omega mesurée (rad par s)', [30 128 60 142]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'couple appliqué (N.m)', [30 255 60 269]);
ajouter(s, 'simulink/Math Operations/Sum', 'Erreur d''angle', [230 45 250 105], 'Inputs', '+-', 'IconShape', 'rectangular', 'ShowName', 'off');
ajouter(s, 'simulink/Math Operations/Sum', 'Erreur de vitesse', [230 120 250 180], 'Inputs', '+-', 'IconShape', 'rectangular', 'ShowName', 'off');
ajouter(s, 'simulink/Math Operations/Gain', 'l2', [300 60 360 90], 'Gain', 'l2_axe(:)');
ajouter(s, 'simulink/Math Operations/Gain', 'l1', [300 135 360 165], 'Gain', 'l1_axe(:)');
ajouter(s, 'simulink/Math Operations/Sum', 'Le', [410 37 430 187], 'Inputs', '++', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Gain', 'lambda', [500 157 560 187], 'Gain', 'lambda_axe(:)');
integrateur(s, 'z3', [600 157 640 187], '0');
ajouter(s, 'simulink/Math Operations/Sum', 'd estimée = Le + z3', [700 82 720 202], 'Inputs', '++', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Gain', 'a0', [760 247 820 277], 'Gain', 'a0_axe(:)');
ajouter(s, 'simulink/Math Operations/Gain', 'a1', [760 367 820 397], 'Gain', 'a1_axe(:)');
ajouter(s, 'simulink/Math Operations/Sum', 'Dérivée de omega estimée', [880 82 900 442], 'Inputs', '++-', 'IconShape', 'rectangular');
integrateur(s, 'omega estimée', [960 247 1000 277], '0');
integrateur(s, 'theta estimée', [1090 247 1130 277], 'q0_deg(:)*pi/180');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'theta estimée (rad)', [1240 255 1270 269]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'omega estimée (rad par s)', [1240 353 1270 367]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'd estimée (rad par s²)', [1240 453 1270 467]);
relier(s, 'theta mesurée (rad)/1', 'Erreur d''angle/1');
depuis(s, 'theta_est', [130 78 200 102], 'Erreur d''angle/2');
relier(s, 'omega mesurée (rad par s)/1', 'Erreur de vitesse/1');
depuis(s, 'omega_est', [130 153 200 177], 'Erreur de vitesse/2');
relier(s, 'Erreur d''angle/1', 'l2/1');
relier(s, 'Erreur de vitesse/1', 'l1/1');
relier(s, 'l2/1', 'Le/1');
relier(s, 'l1/1', 'Le/2');
relier(s, 'Le/1', 'd estimée = Le + z3/1', 'Le');
coude(s, 'Le/1', 'lambda/1', 465);
relier(s, 'lambda/1', 'z3/1');
relier(s, 'z3/1', 'd estimée = Le + z3/2');
relier(s, 'd estimée = Le + z3/1', 'Dérivée de omega estimée/1');
vers(s, 'd estimée = Le + z3/1', 'd_est', [760 28 840 52]);
relier(s, 'couple appliqué (N.m)/1', 'a0/1');
relier(s, 'a0/1', 'Dérivée de omega estimée/2');
depuis(s, 'omega_est', [640 370 720 394], 'a1/1');
relier(s, 'a1/1', 'Dérivée de omega estimée/3');
relier(s, 'Dérivée de omega estimée/1', 'omega estimée/1');
relier(s, 'omega estimée/1', 'theta estimée/1');
relier(s, 'theta estimée/1', 'theta estimée (rad)/1');
ajouter(s, 'simulink/Signal Routing/Goto', 'Goto omega_est', [1070 308 1150 332], 'GotoTag', 'omega_est', 'ShowName', 'off');
coude(s, 'omega estimée/1', 'Goto omega_est/1', 1040);
ajouter(s, 'simulink/Signal Routing/Goto', 'Goto theta_est', [1200 308 1280 332], 'GotoTag', 'theta_est', 'ShowName', 'off');
coude(s, 'theta estimée/1', 'Goto theta_est/1', 1170);
depuis(s, 'omega_est', [1120 348 1200 372], 'omega estimée (rad par s)/1');
depuis(s, 'd_est', [1120 448 1200 472], 'd estimée (rad par s²)/1');
note(s, [30 500], {'Observateur CFO d''un axe, comme dans le TP2.', ...
    'Erreurs d''estimation : e_theta = theta mesurée - theta estimée, e_omega = omega mesurée - omega estimée.          Le = l2 e_theta + l1 e_omega.', ...
    'd(theta estimée)/dt = omega estimée.', ...
    'd(omega estimée)/dt = -a1 omega estimée + a0 C + Le + z3.', ...
    'dz3/dt = lambda Le.', ...
    'Perturbation estimée : d estimée = Le + z3.', ...
    'Gains : l1 = 9 wo, l2 = 12 wo², lambda = 4/3 wo : pôles en -wo et -4 wo (double), à a1 près.', ...
    'Les trois intégrateurs sont discrets (Euler, période T_chn).'});
end

function loi_commande(s)
n = {'theta de référence (rad)', 'theta_ref'; 'vitesse de référence (rad par s)', 'dtheta_ref'; 'accélération de référence (rad par s²)', 'ddtheta_ref'; ...
     'theta estimée (rad)', 'theta_est'; 'omega estimée (rad par s)', 'omega_est'; 'd estimée (rad par s²)', 'd_est'};
for k = 1:6
    y = 50 + 60*(k - 1);
    ajouter(s, 'simulink/Ports & Subsystems/In1', n{k, 1}, [30 y - 7 60 y + 7]);
    vers(s, [n{k, 1} '/1'], n{k, 2}, [170 y - 12 270 y + 12]);
end
ajouter(s, 'simulink/Math Operations/Sum', 'Erreur d''angle', [560 40 580 100], 'Inputs', '+-', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Sum', 'Erreur de vitesse', [560 130 580 190], 'Inputs', '+-', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Gain', 'k1', [640 55 700 85], 'Gain', 'k1_axe(:)');
ajouter(s, 'simulink/Math Operations/Gain', 'k2', [640 145 700 175], 'Gain', 'k2_axe(:)');
ajouter(s, 'simulink/Math Operations/Gain', 'a1', [640 325 700 355], 'Gain', 'a1_axe(:)');
ajouter(s, 'simulink/Math Operations/Sum', 'Somme', [790 25 810 475], 'Inputs', '---++', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Gain', '1 sur a0', [880 235 950 265], 'Gain', '1./a0_axe(:)');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'couple calculé (N.m)', [1030 243 1060 257]);
depuis(s, 'theta_est', [430 43 520 67], 'Erreur d''angle/1');
depuis(s, 'theta_ref', [430 73 520 97], 'Erreur d''angle/2');
depuis(s, 'omega_est', [430 133 520 157], 'Erreur de vitesse/1');
depuis(s, 'dtheta_ref', [430 163 520 187], 'Erreur de vitesse/2');
relier(s, 'Erreur d''angle/1', 'k1/1');
relier(s, 'Erreur de vitesse/1', 'k2/1');
relier(s, 'k1/1', 'Somme/1');
relier(s, 'k2/1', 'Somme/2');
depuis(s, 'd_est', [560 238 650 262], 'Somme/3');
depuis(s, 'dtheta_ref', [500 328 590 352], 'a1/1');
relier(s, 'a1/1', 'Somme/4');
depuis(s, 'ddtheta_ref', [560 418 650 442], 'Somme/5');
relier(s, 'Somme/1', '1 sur a0/1');
relier(s, '1 sur a0/1', 'couple calculé (N.m)/1');
note(s, [30 520], {'Loi de commande d''un axe, comme dans le TP2.', ...
    'Erreurs de suivi : e1 = theta estimée - theta de référence, e2 = omega estimée - vitesse de référence.', ...
    'Commande virtuelle : -k1 e1 - k2 e2, avec k1 = wc² et k2 = 2 xi wc - a1. L''erreur suit alors s² + 2 xi wc s + wc².', ...
    'Couple : C = (-k1 e1 - k2 e2 - d estimée + a1 vitesse de référence + accélération de référence) / a0.'});
end

function limite(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'couple calculé (N.m)', [30 53 60 67]);
ajouter(s, 'simulink/Discontinuities/Saturation', 'Couple maximal', [150 45 210 75], 'UpperLimit', 'C_max', 'LowerLimit', '-C_max');
ajouter(s, 'simulink/Sources/Step', 'Marche à t_depart', [150 115 180 145], 'Time', 't_depart', 'Before', '0', 'After', '1', 'SampleTime', 'T_chn');
ajouter(s, 'simulink/Math Operations/Product', 'x marche', [300 45 330 145], 'Inputs', '2', 'ShowName', 'off');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'couple appliqué (N.m)', [420 88 450 102]);
relier(s, 'couple calculé (N.m)/1', 'Couple maximal/1');
relier(s, 'Couple maximal/1', 'x marche/1');
relier(s, 'Marche à t_depart/1', 'x marche/2');
relier(s, 'x marche/1', 'couple appliqué (N.m)/1');
note(s, [30 210], {'Le couple est borné à C_max : au-delà, les roues devraient accélérer plus vite que acc_roue_max.', ...
    'Avant t_depart, le couple demandé est nul : le dispositif est tenu à la main et les roues se mettent en rotation.'});
end

%% ===================================================================== commande bas niveau : lecture de la consigne à sa période
function commande_bas_niveau(s)
e = [s '/+ consigne d''essai'];
if ~isempty(find_system(e, 'SearchDepth', 1, 'Name', 'Lecture de la vitesse'))
    return
end
n = {'vitesse demandée (rad par s)', '+ vitesse d''essai', 'Lecture de la vitesse'; ...
     'accélération demandée (rad par s²)', '+ accélération d''essai', 'Lecture de l''accélération'};
for k = 1:2
    delete_line(e, [n{k, 1} '/1'], [n{k, 2} '/1']);
    p = get_param([e '/' n{k, 1}], 'Position'); y = (p(2) + p(4))/2;
    ajouter(e, 'simulink/Discrete/Zero-Order Hold', n{k, 3}, [150 y - 15 200 y + 15], 'SampleTime', 'T_cbn', 'ShowName', 'off');
    relier(e, [n{k, 1} '/1'], [n{k, 3} '/1']);
    relier(e, [n{k, 3} '/1'], [n{k, 2} '/1']);
end
end

%% ===================================================================== jumeau Simscape : tenue au départ et perturbation
function procede_simscape(m)
if ~isempty(find_system(m, 'SearchDepth', 1, 'Name', 'Poussée et tenue à la main'))
    return
end
% angles et vitesses du cardan, repris pour la tenue à la main
vers(m, 'Mux angles/1', 'angles_deg', [1470 15 1560 35]);
vers(m, 'Mux vitesses/1', 'vitesses_dps', [1470 115 1560 135]);
% couple extérieur sur les deux axes : tenue à la main jusqu'à t_lacher, puis poussée d'essai
b = [m '/Poussée et tenue à la main'];
add_block('built-in/Subsystem', b, 'Position', [330 500 500 590]);
set_param(b, 'ContentPreviewEnabled', 'off');
pousse_et_tenue(b);
depuis(m, 'angles_deg', [200 511 300 535], 'Poussée et tenue à la main/1');
depuis(m, 'vitesses_dps', [200 556 300 580], 'Poussée et tenue à la main/2');
ajouter(m, 'simulink/Signal Routing/Demux', 'Axes du couple extérieur', [550 515 555 575], 'Outputs', '2', 'ShowName', 'off');
relier(m, 'Poussée et tenue à la main/1', 'Axes du couple extérieur/1');
vers(m, 'Axes du couple extérieur/1', 'c_roulis', [600 518 670 542]);
vers(m, 'Axes du couple extérieur/2', 'c_tangage', [600 548 670 572]);
axes = {'Roulis', 'roulis'; 'Tangage', 'tangage'};
for k = 1:2
    j = [m '/' axes{k, 1}]; a = axes{k, 2};
    set_param(j, 'TorqueActuationMode', 'InputTorque');
    ph = get_param(j, 'PortHandles');
    libre = ph.LConn(arrayfun(@(h) get_param(h, 'Line') == -1, ph.LConn));
    assert(isscalar(libre), 'port de couple introuvable');
    c = get_param(libre, 'Position');
    cv = ajouter(m, 'nesl_utility/Simulink-PS Converter', ['couple ' a], [c(1) - 50 c(2) - 10 c(1) - 30 c(2) + 10], 'Unit', 'N*m', 'ShowName', 'off');
    depuis(m, ['c_' a], [c(1) - 128 c(2) - 10 c(1) - 62 c(2) + 10], ['couple ' a '/1']);
    add_line(m, get_param(cv, 'PortHandles').RConn(1), libre, 'autorouting', 'smart');
end
end

function pousse_et_tenue(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'angles du cardan (°)', [30 73 60 87]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'vitesses du cardan (° par s)', [30 163 60 177]);
ajouter(s, 'simulink/Sources/Constant', 'Position de départ', [30 30 110 50], 'Value', 'q0_deg(:)');
ajouter(s, 'simulink/Math Operations/Sum', 'Écart à la position de départ', [170 30 190 90], 'Inputs', '+-', 'IconShape', 'rectangular', 'ShowName', 'off');
ajouter(s, 'simulink/Math Operations/Gain', 'Raideur de la main', [250 45 330 75], 'Gain', 'k_main*pi/180');
ajouter(s, 'simulink/Math Operations/Gain', 'Amortissement de la main', [250 155 330 185], 'Gain', 'c_main*pi/180');
ajouter(s, 'simulink/Math Operations/Sum', 'Couple de la main', [420 40 440 190], 'Inputs', '+-', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Sources/Step', 'Tenu jusqu''à t_lacher', [420 235 450 265], 'Time', 't_lacher', 'Before', '1', 'After', '0', 'SampleTime', '0');
ajouter(s, 'simulink/Math Operations/Product', 'x tenu', [530 100 560 260], 'Inputs', '2', 'ShowName', 'off');
ajouter(s, 'simulink/Sources/Step', 'Début de la poussée', [530 315 560 345], 'Time', 'perturbation_t', 'Before', '[0; 0]', ...
    'After', 'perturbation_couple(:)', 'SampleTime', '0');
ajouter(s, 'simulink/Sources/Step', 'Fin de la poussée', [530 395 560 425], 'Time', 'perturbation_t + perturbation_duree', 'Before', '[0; 0]', ...
    'After', '-perturbation_couple(:)', 'SampleTime', '0');
ajouter(s, 'simulink/Math Operations/Sum', 'Couple extérieur', [660 140 680 450], 'Inputs', '+++', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'couple sur les axes (N.m)', [760 288 790 302]);
relier(s, 'Position de départ/1', 'Écart à la position de départ/1');
relier(s, 'angles du cardan (°)/1', 'Écart à la position de départ/2');
relier(s, 'Écart à la position de départ/1', 'Raideur de la main/1');
relier(s, 'vitesses du cardan (° par s)/1', 'Amortissement de la main/1');
relier(s, 'Raideur de la main/1', 'Couple de la main/1');
relier(s, 'Amortissement de la main/1', 'Couple de la main/2');
relier(s, 'Couple de la main/1', 'x tenu/1');
relier(s, 'Tenu jusqu''à t_lacher/1', 'x tenu/2');
relier(s, 'x tenu/1', 'Couple extérieur/1');
relier(s, 'Début de la poussée/1', 'Couple extérieur/2');
relier(s, 'Fin de la poussée/1', 'Couple extérieur/3');
relier(s, 'Couple extérieur/1', 'couple sur les axes (N.m)/1');
note(s, [30 490], {'Couple extérieur sur le roulis et sur le tangage, pour les essais.', ...
    'Tenue à la main : jusqu''à t_lacher, un ressort amorti (k_main, c_main) garde le dispositif à sa position de départ.', ...
    'Poussée : le couple perturbation_couple est appliqué de perturbation_t à perturbation_t + perturbation_duree.'});
end

%% ===================================================================== niveau haut
function niveau_haut(nom)
set_param(nom, 'StopTime', '20');
a = find_system(nom, 'FindAll', 'on', 'SearchDepth', 1, 'Type', 'annotation');
for k = 1:numel(a)
    t = get_param(a(k), 'Text');
    if contains(t, 'Remplis à cette étape')
        lignes = strsplit(t, newline);
        j = find(contains(lignes, 'Remplis à cette étape'), 1);
        lignes{j} = ['Toute la chaîne est remplie : référence (polynômes de degré 5), commande haut niveau (CFO par axe), conversion (couples vers les 4 roues), ' ...
            'commande bas niveau (CFO par roue).'];
        lignes = [lignes(1:j), {'Essai : le dispositif est tenu jusqu''à t_lacher, la commande démarre à t_depart, une poussée arrive à perturbation_t (Model Workspace).'}, lignes(j + 1:end)];
        set_param(a(k), 'Text', strjoin(lignes, newline));
        p = get_param(a(k), 'Position');
        set_param(a(k), 'Position', [p(1) p(2) p(3) p(4) + 18]);
    end
end
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

function integrateur(s, n, pos, ci)
ajouter(s, 'simulink/Discrete/Discrete-Time Integrator', n, pos, 'IntegratorMethod', 'Integration: Forward Euler', ...
    'gainval', '1', 'InitialCondition', ci, 'SampleTime', 'T_chn');
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

function vider(s)
% Efface le contenu d'un sous-système en gardant ses ports : les liaisons du niveau au-dessus restent en place.
delete_line(find_system(s, 'SearchDepth', 1, 'FindAll', 'on', 'Type', 'line'));
b = find_system(s, 'SearchDepth', 1, 'Type', 'block');
for k = 2:numel(b)
    if ~any(strcmp(get_param(b{k}, 'BlockType'), {'Inport', 'Outport'})), delete_block(b{k}); end
end
delete(find_system(s, 'SearchDepth', 1, 'FindAll', 'on', 'Type', 'annotation'));
end

function script_fonction(blk, lignes, params)
ch = sfroot().find('-isa', 'Stateflow.EMChart', 'Path', blk);
ch.Script = strjoin(lignes, newline);
for k = 1:numel(params)
    d = ch.find('-isa', 'Stateflow.Data', 'Name', params{k});
    d.Scope = 'Parameter';
end
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

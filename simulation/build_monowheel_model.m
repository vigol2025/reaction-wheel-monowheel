function build_monowheel_model()
%BUILD_MONOWHEEL_MODEL Construit le modèle Simulink monowheel_rw.slx (stabilisation par 4 roues de réaction).
%
%   Même organisation que TP1_SIM :
%   generer_consigne -> Commande_haut_niveau (retour d'état) -> Allocation (convertisseur)
%   -> Moteur_1..4 (commande de vitesse + ESO) -> Corps_robot (modèle dynamique) -> IMU -> retour.
%
%   Usage : build_monowheel_model, puis run_monowheel (ou ouvrir monowheel_rw.slx et lancer).

mdl = 'monowheel_rw';
here = fileparts(mfilename('fullpath'));
if bdIsLoaded(mdl), close_system(mdl, 0); end
f = fullfile(here, [mdl '.slx']);
if exist(f, 'file'), delete(f); end
new_system(mdl);
P = params_monowheel('robot_final'); %#ok<NASGU> % pour la compilation pendant la construction
assignin('base', 'P', params_monowheel('robot_final'));

%% ===================== Niveau supérieur (disposition manuelle, étiquettes Goto/From comme TP1_SIM) =====================
% --- Consigne et perturbations ---
blk(mdl, 'simulink/Sources/Clock', 'Horloge', 'Position', [20 120 50 150]);
blk(mdl, 'simulink/Sources/Constant', 'pert', 'Value', 'P.scen.pert', 'Position', [20 185 90 215]);
mfun(mdl, 'generer_consigne', {
    'function Td = generer_consigne(t, pert)'
    '% Poussées calibrées sur le corps : couple de perturbation (N.m)'
    '% pert = [t1 durée1 couple_roulis  t2 durée2 couple_tangage]'
    'Td = zeros(2, 1);'
    'if t >= pert(1) && t < pert(1) + pert(2), Td(1) = pert(3); end'
    'if t >= pert(4) && t < pert(4) + pert(5), Td(2) = pert(6); end'
    });
set_param([mdl '/generer_consigne'], 'Position', [140 110 280 230]);
ligne(mdl, 'Horloge/1', 'generer_consigne/1');
ligne(mdl, 'pert/1', 'generer_consigne/2');
etiquette(mdl, 'Goto', 'Tdist', [320 160 390 180]);
ligne(mdl, 'generer_consigne/1', 'Goto_Tdist/1', 'Tdist');

% --- Commande haute et allocation ---
build_commande(mdl);
set_param([mdl '/Commande_haut_niveau'], 'Position', [540 110 720 400]);
etiquette(mdl, 'From', 'angle_m', [410 148 490 168]);
etiquette(mdl, 'From', 'vitesse_m', [410 245 490 265]);
blk(mdl, 'simulink/Signal Routing/Mux', 'Mux_w_est', 'Inputs', '4', 'Position', [490 272 495 432]);
for k = 1:4
    etiquette(mdl, 'From', sprintf('w_est_%d', k), [380 284 + (k - 1) * 40 460 300 + (k - 1) * 40]);
    ligne(mdl, sprintf('From_w_est_%d/1', k), sprintf('Mux_w_est/%d', k));
end
ligne(mdl, 'From_angle_m/1', 'Commande_haut_niveau/1', 'angle_m');
ligne(mdl, 'From_vitesse_m/1', 'Commande_haut_niveau/2', 'vitesse_m');
ligne(mdl, 'Mux_w_est/1', 'Commande_haut_niveau/3', 'w_est');
build_allocation(mdl);
set_param([mdl '/Allocation'], 'Position', [780 195 900 315]);
ligne(mdl, 'Commande_haut_niveau/1', 'Allocation/1', 'v');
etiquette(mdl, 'Goto', 'v', [780 360 840 380]);
ligne(mdl, 'Commande_haut_niveau/1', 'Goto_v/1');
etiquette(mdl, 'Goto', 'wr', [940 215 1010 235]);
etiquette(mdl, 'Goto', 'wr_point', [940 275 1010 295]);
ligne(mdl, 'Allocation/1', 'Goto_wr/1', 'wr');
ligne(mdl, 'Allocation/2', 'Goto_wr_point/1', 'wr_point');

% --- Les 4 boucles moteur ---
build_moteur(mdl, 'Moteur_1');
for k = 2:4
    add_block([mdl '/Moteur_1'], sprintf('%s/Moteur_%d', mdl, k));
end
sorties = {'w', 'w_est', 'tau', 'i', 'V'};
entrees = {'wr', 'wr_point', 'couplage'};
for k = 1:4
    y0 = 40 + (k - 1) * 260; M = sprintf('Moteur_%d', k);
    set_param([mdl '/' M], 'Position', [1200 y0 1370 y0 + 200]);
    for j = 1:3
        yc = y0 + round(200 * (j - 0.5) / 3);
        etiquette(mdl, 'From', entrees{j}, [1030 yc - 10 1100 yc + 10], sprintf('%s_%d', entrees{j}, k));
        selection(mdl, sprintf('Sel_%s_%d', entrees{j}, k), k, [1120 yc - 10 1160 yc + 10]);
        ligne(mdl, sprintf('From_%s_%d/1', entrees{j}, k), sprintf('Sel_%s_%d/1', entrees{j}, k));
        ligne(mdl, sprintf('Sel_%s_%d/1', entrees{j}, k), sprintf('%s/%d', M, j));
    end
    for j = 1:5
        yc = y0 + 20 + (j - 1) * 40;
        etiquette(mdl, 'Goto', sprintf('%s_%d', sorties{j}, k), [1410 yc - 9 1480 yc + 9]);
        ligne(mdl, sprintf('%s/%d', M, j), sprintf('Goto_%s_%d/1', sorties{j}, k));
    end
end

% --- Corps du robot et IMU ---
build_corps(mdl);
set_param([mdl '/Corps_robot'], 'Position', [1680 90 1840 290]);
blk(mdl, 'simulink/Signal Routing/Mux', 'Mux_tau', 'Inputs', '4', 'Position', [1620 60 1625 220]);
for k = 1:4
    etiquette(mdl, 'From', sprintf('tau_%d', k), [1530 72 + (k - 1) * 40 1600 88 + (k - 1) * 40]);
    ligne(mdl, sprintf('From_tau_%d/1', k), sprintf('Mux_tau/%d', k));
end
ligne(mdl, 'Mux_tau/1', 'Corps_robot/1', 'tau');
etiquette(mdl, 'From', 'Tdist', [1530 230 1600 250], 'Tdist_corps');
ligne(mdl, 'From_Tdist_corps/1', 'Corps_robot/2', 'Tdist');
build_imu(mdl);
set_param([mdl '/IMU'], 'Position', [2000 100 2140 210]);
ligne(mdl, 'Corps_robot/1', 'IMU/1', 'Theta');
ligne(mdl, 'Corps_robot/2', 'IMU/2', 'Theta_dot');
etiquette(mdl, 'Goto', 'Theta', [1900 30 1970 50]);
etiquette(mdl, 'Goto', 'Theta_dot', [1900 320 1970 340]);
ligne(mdl, 'Corps_robot/1', 'Goto_Theta/1');
ligne(mdl, 'Corps_robot/2', 'Goto_Theta_dot/1');
etiquette(mdl, 'Goto', 'angle_m', [2180 118 2260 138]);
etiquette(mdl, 'Goto', 'vitesse_m', [2180 173 2260 193]);
ligne(mdl, 'IMU/1', 'Goto_angle_m/1', 'angle_m');
ligne(mdl, 'IMU/2', 'Goto_vitesse_m/1', 'vitesse_m');
blk(mdl, 'simulink/Math Operations/Gain', 'Projection_Bt', 'Gain', 'P.B''', 'Multiplication', 'Matrix(K*u)', ...
    'Position', [2000 380 2060 410]);
ligne(mdl, 'Corps_robot/3', 'Projection_Bt/1', 'Theta_ddot');
etiquette(mdl, 'Goto', 'couplage', [2100 385 2180 405]);
ligne(mdl, 'Projection_Bt/1', 'Goto_couplage/1', 'couplage');

% --- Arrêt si le robot tombe ---
etiquette(mdl, 'From', 'Theta', [1530 520 1600 540], 'Theta_chute');
blk(mdl, 'simulink/Math Operations/Abs', 'Abs', 'Position', [1640 515 1670 545]);
blk(mdl, 'simulink/Math Operations/MinMax', 'Max', 'Function', 'max', 'Inputs', '1', 'Position', [1710 515 1740 545]);
blk(mdl, 'simulink/Sources/Constant', 'angle_chute', 'Value', 'P.scen.angle_chute', 'Position', [1640 580 1740 600]);
blk(mdl, 'simulink/Logic and Bit Operations/Relational Operator', 'Chute', 'Operator', '>', 'Position', [1790 520 1820 560]);
blk(mdl, 'simulink/Sinks/Stop Simulation', 'Stop', 'Position', [1870 525 1900 555]);
ligne(mdl, 'From_Theta_chute/1', 'Abs/1');
ligne(mdl, 'Abs/1', 'Max/1');
ligne(mdl, 'Max/1', 'Chute/1');
ligne(mdl, 'angle_chute/1', 'Chute/2');
ligne(mdl, 'Chute/1', 'Stop/1');

% --- Enregistrement et visualisation (bande du bas) ---
yb = 1150;
journal_from(mdl, 'Theta', 'Theta', [40 yb]);
journal_from(mdl, 'Theta_dot', 'Theta_dot', [40 yb + 60]);
journal_from(mdl, 'v', 'v', [40 yb + 120]);
journal_from(mdl, 'Tdist', 'Tdist', [40 yb + 180]);
journal_from(mdl, 'wr', 'wr', [40 yb + 240]);
blk(mdl, 'simulink/Math Operations/Gain', 'rad2deg', 'Gain', '180/pi', 'Position', [330 yb + 35 370 yb + 65]);
blk(mdl, 'simulink/Sinks/Scope', 'Angles_deg', 'Position', [410 yb + 35 440 yb + 65]);
ligne(mdl, 'From_log_Theta/1', 'rad2deg/1');
ligne(mdl, 'rad2deg/1', 'Angles_deg/1');
groupe = {'w', 'Vitesses_roues'; 'i', 'Courants'; 'V', ''};
for g = 1:3
    x0 = 600 + (g - 1) * 420; var = groupe{g, 1};
    mx = sprintf('Mux_%s', var);
    blk(mdl, 'simulink/Signal Routing/Mux', mx, 'Inputs', '4', 'Position', [x0 + 110 yb x0 + 115 yb + 160]);
    for k = 1:4
        etiquette(mdl, 'From', sprintf('%s_%d', var, k), [x0 yb + 12 + (k - 1) * 40 x0 + 70 yb + 28 + (k - 1) * 40], ...
            sprintf('log_%s_%d', var, k));
        ligne(mdl, sprintf('From_log_%s_%d/1', var, k), sprintf('%s/%d', mx, k));
    end
    add_block('simulink/Sinks/To Workspace', [mdl '/log_' var], 'VariableName', var, 'SaveFormat', 'Timeseries', ...
        'Position', [x0 + 170 yb + 50 x0 + 250 yb + 70]);
    ligne(mdl, [mx '/1'], ['log_' var '/1'], var);
    if ~isempty(groupe{g, 2})
        blk(mdl, 'simulink/Sinks/Scope', groupe{g, 2}, 'Position', [x0 + 170 yb + 100 x0 + 200 yb + 130]);
        ligne(mdl, [mx '/1'], [groupe{g, 2} '/1']);
    end
end

note(mdl, {
    'Stabilisation du monowheel Crystof par 4 roues de réaction à 45 degrés'
    ''
    'Chaîne : consigne et perturbations -> commande haute par retour d''état (LQR ou placement de pôles)'
    '-> allocation pseudo-inverse sur les 4 roues -> 4 boucles moteur (vitesse + observateur ESO)'
    '-> modèle dynamique du corps (pendule inversé sur 2 axes) -> IMU (BNO055, 100 Hz, bruit, biais).'
    'Les liaisons entre groupes passent par des étiquettes Goto/From : même nom, même signal.'
    ''
    'Paramètres : P = params_monowheel(''robot_final'' | ''robot_A2212'' | ''banc_1axe'')'
    'Choix de la loi de commande : P.ctrl_mode = 1 (LQR) ou 2 (placement de pôles)'
    'Lancement des scénarios et des figures : run_monowheel'
    });
an = find_system(mdl, 'SearchDepth', 1, 'FindAll', 'on', 'Type', 'annotation');
for k = 1:numel(an)
    p = get_param(an(k), 'Position');
    set_param(an(k), 'Position', [20 520 20 + (p(3) - p(1)) 520 + (p(4) - p(2))]);
end

% --- Noms lisibles sous les étiquettes (le texte des icônes ne s'imprime pas toujours) ---
renommer_etiquettes(mdl);

%% ===================== Réglages du modèle =====================
set_param(mdl, 'StopTime', 'P.scen.Tf', 'Solver', 'ode45', 'MaxStep', '1e-3', 'RelTol', '1e-4', ...
    'ReturnWorkspaceOutputs', 'on', 'SaveOutput', 'off', 'SaveTime', 'off', ...
    'InitFcn', sprintf(['addpath(fileparts(get_param(bdroot, ''FileName'')));\n' ...
    'if ~exist(''P'', ''var''), P = params_monowheel(''robot_final''); end']));
save_system(mdl, f);
fprintf('Modèle enregistré : %s\n', f);
end

%% ===================== Sous-systèmes =====================
function build_commande(mdl)
s = sub(mdl, 'Commande_haut_niveau', {'angle_m', 'vitesse_m', 'w_est'}, {'v'});
blk(s, 'simulink/Math Operations/Gain', 'Projection_B', 'Gain', 'P.B', 'Multiplication', 'Matrix(K*u)');
blk(s, 'simulink/Signal Routing/Mux', 'Etat_z', 'Inputs', '3');
blk(s, 'simulink/Math Operations/Gain', 'K_LQR', 'Gain', '-P.K_lqr', 'Multiplication', 'Matrix(K*u)');
blk(s, 'simulink/Math Operations/Gain', 'K_placement', 'Gain', '-P.K_pp', 'Multiplication', 'Matrix(K*u)');
blk(s, 'simulink/Sources/Constant', 'ctrl_mode', 'Value', 'P.ctrl_mode');
blk(s, 'simulink/Signal Routing/Multiport Switch', 'Choix_loi', 'Inputs', '2', 'DataPortOrder', 'One-based contiguous');
blk(s, 'simulink/Discontinuities/Saturation', 'Sat_couple', 'UpperLimit', 'P.v_max', 'LowerLimit', '-P.v_max');
ligne(s, 'w_est/1', 'Projection_B/1', 'W');
ligne(s, 'angle_m/1', 'Etat_z/1');
ligne(s, 'vitesse_m/1', 'Etat_z/2');
ligne(s, 'Projection_B/1', 'Etat_z/3');
ligne(s, 'Etat_z/1', 'K_LQR/1', 'z');
ligne(s, 'Etat_z/1', 'K_placement/1');
ligne(s, 'ctrl_mode/1', 'Choix_loi/1');
ligne(s, 'K_LQR/1', 'Choix_loi/2');
ligne(s, 'K_placement/1', 'Choix_loi/3');
ligne(s, 'Choix_loi/1', 'Sat_couple/1');
ligne(s, 'Sat_couple/1', 'v/1', 'v');
note(s, {
    'Commande haute : retour d''état (un par axe)'
    ''
    'États par axe : angle, vitesse angulaire, W = B*w (vitesse projetée des roues)'
    'z = [phi ; theta ; phi'' ; theta'' ; Wx ; Wy],  v = -K z  (v = B*tau, couple de réaction demandé)'
    ''
    'Modèle de synthèse (par axe) :'
    '  angle'''' = (m g h / Jp) angle - v / Jp'
    '  W''      = v / Jr - (B B^T) angle'''''
    ''
    'K_LQR : lqr(A, B, Q, R), règle de Bryson (P.lqr_w)'
    'K_placement : place(A, B, P.pp_poles)'
    'Choix par P.ctrl_mode (1 = LQR, 2 = placement) ; saturation à P.v_max'
    });
arrange(s);
end

function build_allocation(mdl)
s = sub(mdl, 'Allocation', {'v'}, {'wr', 'wr_point'});
blk(s, 'simulink/Math Operations/Gain', 'Pseudo_inverse', 'Gain', 'P.Bpinv', 'Multiplication', 'Matrix(K*u)');
blk(s, 'simulink/Math Operations/Gain', 'Inv_Jr', 'Gain', '1/P.mot.Jr');
blk(s, 'simulink/Continuous/Integrator', 'Integ_wr', 'InitialCondition', 'zeros(4,1)', 'LimitOutput', 'on', ...
    'UpperSaturationLimit', '0.9*P.mot.wmax', 'LowerSaturationLimit', '-0.9*P.mot.wmax');
ligne(s, 'v/1', 'Pseudo_inverse/1');
ligne(s, 'Pseudo_inverse/1', 'Inv_Jr/1', 'tau_r');
ligne(s, 'Inv_Jr/1', 'Integ_wr/1');
ligne(s, 'Inv_Jr/1', 'wr_point/1', 'wr_point');
ligne(s, 'Integ_wr/1', 'wr/1', 'wr');
note(s, {
    'Allocation (convertisseur) : couple demandé par axe -> consignes des 4 roues'
    ''
    'tau_r = pinv(B) v    (norme minimale, B B^T = 2 I pour 4 roues à 45 degrés)'
    'wr_point = tau_r / Jr,  wr = intégrale de wr_point (bornée à 0,9 wmax)'
    'La boucle de vitesse de chaque moteur suit wr avec l''anticipation wr_point :'
    'le moteur produit alors le couple tau_r.'
    });
arrange(s);
end

function build_moteur(mdl, nom)
s = sub(mdl, nom, {'wr', 'wr_point', 'couplage'}, {'w', 'w_est', 'tau', 'i', 'V'});

% --- Control_moteur ---
c = sub(s, 'Control_moteur', {'wr_point', 'wr', 'w', 'd_est'}, {'V'});
blk(c, 'simulink/Math Operations/Sum', 'Erreur', 'Inputs', '+-');
blk(c, 'simulink/Math Operations/Gain', 'Kv', 'Gain', 'P.mot.Kv');
blk(c, 'simulink/Math Operations/Gain', 'a0', 'Gain', 'P.mot.a0');
blk(c, 'simulink/Math Operations/Sum', 'Somme', 'Inputs', '---+');
blk(c, 'simulink/Math Operations/Gain', 'Inv_b0', 'Gain', '1/P.mot.b0');
blk(c, 'simulink/Discontinuities/Saturation', 'Sat_V', 'UpperLimit', 'P.mot.Vmax', 'LowerLimit', '-P.mot.Vmax');
ligne(c, 'w/1', 'Erreur/1');
ligne(c, 'wr/1', 'Erreur/2');
ligne(c, 'Erreur/1', 'Kv/1', 'e');
ligne(c, 'w/1', 'a0/1');
ligne(c, 'Kv/1', 'Somme/1');
ligne(c, 'a0/1', 'Somme/2');
ligne(c, 'd_est/1', 'Somme/3');
ligne(c, 'wr_point/1', 'Somme/4');
ligne(c, 'Somme/1', 'Inv_b0/1');
ligne(c, 'Inv_b0/1', 'Sat_V/1');
ligne(c, 'Sat_V/1', 'V/1', 'V');
note(c, {'V = (-Kv e - a0 w - d_est + wr'') / b0,  e = w - wr', 'Saturation : -Vmax <= V <= Vmax'});
arrange(c);

% --- Moteur (modèle réduit avec limitation de courant) ---
m = sub(s, 'Moteur', {'V', 'couplage'}, {'w', 'tau', 'i'});
blk(m, 'simulink/Math Operations/Gain', 'Ke', 'Gain', 'P.mot.Ke');
blk(m, 'simulink/Math Operations/Sum', 'V_moins_fcem', 'Inputs', '+-');
blk(m, 'simulink/Math Operations/Gain', 'Inv_R', 'Gain', '1/P.mot.R');
blk(m, 'simulink/Discontinuities/Saturation', 'Sat_I', 'UpperLimit', 'P.mot.Imax', 'LowerLimit', '-P.mot.Imax');
blk(m, 'simulink/Math Operations/Gain', 'Kt', 'Gain', 'P.mot.Kt');
blk(m, 'simulink/Math Operations/Gain', 'f', 'Gain', 'P.mot.f');
blk(m, 'simulink/Math Operations/Sum', 'Couple_net', 'Inputs', '+-');
blk(m, 'simulink/Math Operations/Gain', 'Inv_Jr', 'Gain', '1/P.mot.Jr');
blk(m, 'simulink/Math Operations/Sum', 'Moins_couplage', 'Inputs', '+-');
blk(m, 'simulink/Continuous/Integrator', 'Integ_w', 'InitialCondition', '0');
ligne(m, 'V/1', 'V_moins_fcem/1');
ligne(m, 'Integ_w/1', 'Ke/1');
ligne(m, 'Ke/1', 'V_moins_fcem/2');
ligne(m, 'V_moins_fcem/1', 'Inv_R/1');
ligne(m, 'Inv_R/1', 'Sat_I/1');
ligne(m, 'Sat_I/1', 'Kt/1', 'i');
ligne(m, 'Sat_I/1', 'i/1');
ligne(m, 'Kt/1', 'Couple_net/1');
ligne(m, 'Integ_w/1', 'f/1');
ligne(m, 'f/1', 'Couple_net/2');
ligne(m, 'Couple_net/1', 'Inv_Jr/1', 'tau');
ligne(m, 'Couple_net/1', 'tau/1');
ligne(m, 'Inv_Jr/1', 'Moins_couplage/1');
ligne(m, 'couplage/1', 'Moins_couplage/2');
ligne(m, 'Moins_couplage/1', 'Integ_w/1');
ligne(m, 'Integ_w/1', 'w/1', 'w');
note(m, {
    'Modèle réduit du moteur (L di/dt = 0) :'
    '  i = sat((V - Ke w) / R, Imax)      limitation de courant de l''ESC'
    '  Jr (w'' + a_i . Theta'''') = Kt i - f w'
    'Le couple net tau = Kt i - f w est renvoyé sur le corps.'
    });
arrange(m);

% --- Observateur ESO ---
o = sub(s, 'Observateur', {'w', 'V'}, {'w_est', 'd_est'});
blk(o, 'simulink/Signal Routing/Mux', 'Entree', 'Inputs', '2');
blk(o, 'simulink/Continuous/State-Space', 'ESO', 'A', 'P.mot.Aeso', 'B', 'P.mot.Beso', 'C', 'eye(2)', 'D', 'zeros(2)');
blk(o, 'simulink/Signal Routing/Demux', 'Sorties', 'Outputs', '2');
ligne(o, 'w/1', 'Entree/1');
ligne(o, 'V/1', 'Entree/2');
ligne(o, 'Entree/1', 'ESO/1');
ligne(o, 'ESO/1', 'Sorties/1');
ligne(o, 'Sorties/1', 'w_est/1', 'w_est');
ligne(o, 'Sorties/2', 'd_est/1', 'd_est');
note(o, {
    'Observateur à état étendu (ESO) : états x1 = w, x2 = d (d'' = 0)'
    '  dx1/dt = a0 x1 + b0 V + x2 + l1 (w - x1)'
    '  dx2/dt = l2 (w - x1)'
    'Gains : place(A_a'', C_a'', P.mot.eso_poles)'''
    });
arrange(o);

% --- Câblage de la boucle moteur ---
ligne(s, 'wr_point/1', 'Control_moteur/1');
ligne(s, 'wr/1', 'Control_moteur/2');
ligne(s, 'Moteur/1', 'Control_moteur/3');
ligne(s, 'Observateur/2', 'Control_moteur/4', 'd_est');
ligne(s, 'Control_moteur/1', 'Moteur/1', 'V');
ligne(s, 'couplage/1', 'Moteur/2');
ligne(s, 'Moteur/1', 'Observateur/1', 'w');
ligne(s, 'Control_moteur/1', 'Observateur/2');
ligne(s, 'Moteur/1', 'w/1');
ligne(s, 'Observateur/1', 'w_est/1', 'w_est');
ligne(s, 'Moteur/2', 'tau/1', 'tau');
ligne(s, 'Moteur/3', 'i/1', 'i');
ligne(s, 'Control_moteur/1', 'V/1');
note(s, {
    'Boucle moteur (une par roue), comme Moteur_d / Moteur_g du TP1_SIM'
    ''
    'Modèle réduit : w'' = a0 w + b0 V + d'
    '  a0 = -(Kt Ke / (Jr R) + f / Jr),  b0 = Kt / (Jr R)'
    '  d regroupe le couplage avec le corps et les erreurs de modèle'
    'Commande de vitesse avec anticipation wr'' et compensation de d estimée par l''ESO'
    });
arrange(s);
end

function build_corps(mdl)
s = sub(mdl, 'Corps_robot', {'tau', 'Tdist'}, {'Theta', 'Theta_dot', 'Theta_ddot'});
blk(s, 'simulink/Math Operations/Gain', 'Moins_B', 'Gain', '-P.B', 'Multiplication', 'Matrix(K*u)');
blk(s, 'simulink/Math Operations/Sum', 'Couple_corps', 'Inputs', '++');
blk(s, 'simulink/Math Operations/Trigonometric Function', 'sin', 'Operator', 'sin');
blk(s, 'simulink/Math Operations/Gain', 'mgh', 'Gain', 'P.corps.mgh');
blk(s, 'simulink/Math Operations/Sum', 'Somme_couples', 'Inputs', '++');
blk(s, 'simulink/Math Operations/Gain', 'Inv_Jp', 'Gain', '1/P.corps.Jp');
blk(s, 'simulink/Math Operations/Gain', 'Axes_actifs', 'Gain', 'P.corps.actif', 'Multiplication', 'Element-wise(K.*u)');
blk(s, 'simulink/Continuous/Integrator', 'Integ_vitesse', 'InitialCondition', 'zeros(2,1)');
blk(s, 'simulink/Continuous/Integrator', 'Integ_angle', 'InitialCondition', 'P.scen.Theta0');
ligne(s, 'tau/1', 'Moins_B/1');
ligne(s, 'Moins_B/1', 'Couple_corps/1');
ligne(s, 'Tdist/1', 'Couple_corps/2');
ligne(s, 'Integ_angle/1', 'sin/1');
ligne(s, 'sin/1', 'mgh/1');
ligne(s, 'mgh/1', 'Somme_couples/1');
ligne(s, 'Couple_corps/1', 'Somme_couples/2');
ligne(s, 'Somme_couples/1', 'Inv_Jp/1');
ligne(s, 'Inv_Jp/1', 'Axes_actifs/1');
ligne(s, 'Axes_actifs/1', 'Integ_vitesse/1', 'Theta_ddot');
ligne(s, 'Axes_actifs/1', 'Theta_ddot/1');
ligne(s, 'Integ_vitesse/1', 'Integ_angle/1', 'Theta_dot');
ligne(s, 'Integ_vitesse/1', 'Theta_dot/1');
ligne(s, 'Integ_angle/1', 'Theta/1', 'Theta');
note(s, {
    'Modèle dynamique du corps : pendule inversé sur 2 axes (roulis, tangage)'
    ''
    '  Jp Theta'''' = m g h sin(Theta) - B tau + Tdist'
    '  Jp : inertie autour du point de contact au sol (Icm + m h^2)'
    '  -B tau : réaction des 4 moteurs sur le corps'
    'P.corps.actif bloque le tangage pour le banc à 1 axe.'
    });
arrange(s);
end

function build_imu(mdl)
s = sub(mdl, 'IMU', {'Theta', 'Theta_dot'}, {'angle_m', 'vitesse_m'});
blk(s, 'simulink/Sources/Random Number', 'Bruit_angle', 'Mean', 'zeros(2,1)', 'Variance', 'P.imu.sig_angle^2*ones(2,1)', ...
    'Seed', 'P.imu.graine(1:2)''', 'SampleTime', 'P.imu.Ts');
blk(s, 'simulink/Sources/Random Number', 'Bruit_gyro', 'Mean', 'zeros(2,1)', 'Variance', 'P.imu.sig_gyro^2*ones(2,1)', ...
    'Seed', 'P.imu.graine(3:4)''', 'SampleTime', 'P.imu.Ts');
blk(s, 'simulink/Sources/Constant', 'Biais', 'Value', 'P.imu.biais_angle');
blk(s, 'simulink/Math Operations/Sum', 'Somme_angle', 'Inputs', '+++');
blk(s, 'simulink/Math Operations/Sum', 'Somme_gyro', 'Inputs', '++');
blk(s, 'simulink/Discrete/Zero-Order Hold', 'Echant_angle', 'SampleTime', 'P.imu.Ts');
blk(s, 'simulink/Discrete/Zero-Order Hold', 'Echant_gyro', 'SampleTime', 'P.imu.Ts');
ligne(s, 'Theta/1', 'Somme_angle/1');
ligne(s, 'Biais/1', 'Somme_angle/2');
ligne(s, 'Bruit_angle/1', 'Somme_angle/3');
ligne(s, 'Somme_angle/1', 'Echant_angle/1');
ligne(s, 'Echant_angle/1', 'angle_m/1', 'angle_m');
ligne(s, 'Theta_dot/1', 'Somme_gyro/1');
ligne(s, 'Bruit_gyro/1', 'Somme_gyro/2');
ligne(s, 'Somme_gyro/1', 'Echant_gyro/1');
ligne(s, 'Echant_gyro/1', 'vitesse_m/1', 'vitesse_m');
note(s, {
    'IMU BNO055 en mode fusion (NDOF), échantillonnée à 100 Hz'
    '  angle mesuré = angle + biais de verticale + bruit'
    '  vitesse mesurée = vitesse angulaire + bruit'
    });
arrange(s);
end

%% ===================== Outils =====================
function s = sub(parent, nom, ins, outs)
s = [parent '/' nom];
add_block('built-in/Subsystem', s);
for k = 1:numel(ins)
    add_block('built-in/Inport', [s '/' ins{k}], 'Port', num2str(k));
end
for k = 1:numel(outs)
    add_block('built-in/Outport', [s '/' outs{k}], 'Port', num2str(k));
end
end

function blk(sys, src, nom, varargin)
add_block(src, [sys '/' nom], varargin{:});
end

function ligne(sys, de, vers, nom)
h = add_line(sys, de, vers, 'autorouting', 'smart');
if nargin > 3, set_param(h, 'Name', nom); end
end

function renommer_etiquettes(sys)
% Goto : nom = étiquette ; From : étiquette + destination ; Selector : consigne(k)
dest = struct('Mux_w_est', 'cmd', 'Commande_haut_niveau', 'cmd', 'Mux_tau', 'corps', ...
    'Corps_robot', 'corps', 'Abs', 'chute');
bl = find_system(sys, 'SearchDepth', 1, 'Regexp', 'on', 'BlockType', 'Goto|From|Selector');
for k = 1:numel(bl)
    b = bl{k}; nom = get_param(b, 'Name'); type = get_param(b, 'BlockType');
    switch type
        case 'Goto'
            neuf = get_param(b, 'GotoTag');
        case 'From'
            tag = get_param(b, 'GotoTag');
            if startsWith(nom, 'From_log_')
                neuf = [tag ' (log)'];
            else
                pc = get_param(b, 'PortConnectivity');
                d = get_param(pc(end).DstBlock(1), 'Name');
                tok = regexp(d, '^Sel_.*_(\d)$', 'tokens', 'once');
                if ~isempty(tok)
                    neuf = sprintf('%s (M%s)', tag, tok{1});
                elseif isfield(dest, d)
                    neuf = sprintf('%s (%s)', tag, dest.(d));
                else
                    neuf = [tag ' (' d ')'];
                end
            end
        case 'Selector'
            tok = regexp(nom, '^Sel_(.*)_(\d)$', 'tokens', 'once');
            neuf = sprintf('%s(%s)', tok{1}, tok{2});
    end
    set_param(b, 'Name', neuf, 'ShowName', 'on');
end
end

function etiquette(sys, type, tag, pos, nom)
% Étiquette Goto ou From, comme les tags du TP1_SIM
if nargin < 5, nom = tag; end
add_block(['simulink/Signal Routing/' type], sprintf('%s/%s_%s', sys, type, nom), 'GotoTag', tag, ...
    'Position', pos, 'ShowName', 'off');
end

function selection(sys, nom, k, pos)
% Extrait la composante k d'un vecteur de 4 consignes
try
    add_block('simulink/Signal Routing/Selector', [sys '/' nom], 'InputPortWidth', '4', 'Indices', num2str(k), ...
        'Position', pos, 'ShowName', 'off');
catch
    e = zeros(1, 4); e(k) = 1;
    add_block('simulink/Math Operations/Gain', [sys '/' nom], 'Gain', mat2str(e), 'Multiplication', 'Matrix(K*u)', ...
        'Position', pos, 'ShowName', 'off');
end
end

function journal_from(sys, tag, var, xy)
% From <tag> -> To Workspace <var>
x = xy(1); y = xy(2);
add_block('simulink/Signal Routing/From', sprintf('%s/From_log_%s', sys, var), 'GotoTag', tag, ...
    'Position', [x y x + 80 y + 20], 'ShowName', 'off');
add_block('simulink/Sinks/To Workspace', [sys '/log_' var], 'VariableName', var, 'SaveFormat', 'Timeseries', ...
    'Position', [x + 130 y x + 210 y + 20]);
add_line(sys, sprintf('From_log_%s/1', var), ['log_' var '/1'], 'autorouting', 'smart');
end

function journal(sys, de, var)
nom = ['log_' var];
add_block('simulink/Sinks/To Workspace', [sys '/' nom], 'VariableName', var, 'SaveFormat', 'Timeseries');
add_line(sys, de, [nom '/1'], 'autorouting', 'smart');
end

function mfun(sys, nom, code)
p = [sys '/' nom];
add_block('simulink/User-Defined Functions/MATLAB Function', p);
ch = find(sfroot, '-isa', 'Stateflow.EMChart', 'Path', p);
ch.Script = strjoin(code, newline);
end

function note(sys, lignes)
try
    a = Simulink.Annotation([sys '/Equations']);
    a.Text = strjoin(lignes, newline);
    a.FontSize = 11;
    a.HorizontalAlignment = 'left';
catch err
    warning('Annotation non créée dans %s : %s', sys, err.message);
end
end

function arrange(sys)
try
    Simulink.BlockDiagram.arrangeSystem(sys);
catch err
    warning('Mise en page automatique impossible pour %s : %s', sys, err.message);
end
% Annotations à droite des blocs, comme dans TP1_SIM
bl = find_system(sys, 'SearchDepth', 1, 'Type', 'Block');
bl = bl(~strcmp(bl, sys));
if isempty(bl), return; end
pos = cell2mat(get_param(bl, 'Position'));
x0 = max(pos(:, 3)) + 80; y0 = min(pos(:, 2));
an = find_system(sys, 'SearchDepth', 1, 'FindAll', 'on', 'Type', 'annotation');
for k = 1:numel(an)
    p = get_param(an(k), 'Position');
    set_param(an(k), 'Position', [x0, y0, x0 + (p(3) - p(1)), y0 + (p(4) - p(2))]);
    y0 = y0 + (p(4) - p(2)) + 20;
end
end

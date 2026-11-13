function construire_perception(fichier)
% Remplit le bloc « Perception » du modèle jumeau_banc_rw.slx : des mesures du banc à son état.
%
% Ce que le script fait :
%   - Perception : angles de roulis et de tangage tirés du quaternion du BNO055 (pas 8 fois plus fin que ses angles
%     d'Euler, et exacts en inclinaison combinée), leurs vitesses tirées du gyroscope, vitesses des 4 roues avec leur signe
%     et leur visibilité par le capteur, moment cinétique des roues, couple extérieur qu'elles absorbent, déséquilibre du
%     banc en mm, réserve des roues ;
%   - Interface sensorielle : le quaternion du BNO055 rejoint les mesures ;
%   - jumeau Simscape : le quaternion du BNO055 reçoit le même bruit de mesure que ses angles d'Euler (le jumeau Webots
%     le fait dans son contrôleur) ;
%   - niveau haut : la Perception reçoit aussi les impulsions envoyées aux ESC (pour donner leur signe aux vitesses).
% Les observateurs CFO restent dans les commandes, comme dans le TP2.
%
% Attention : le contenu du bloc Perception est reconstruit en entier. Les réglages du Model Workspace sont conservés.

if nargin < 1
    fichier = fullfile(fileparts(fileparts(mfilename('fullpath'))), 'jumeau_banc_rw.slx');
end
[~, nom] = fileparts(fichier);
load_system(fichier);
parametres(nom);
bruit_quaternion([nom '/Procédé/Jumeau Simscape/Capteur BNO055']);
interface([nom '/Interface sensorielle']);
perception([nom '/Perception']);
niveau_haut(nom);
save_system(nom, fichier);
close_system(nom, 0);
fprintf('perception en place : %s\n', fichier);
end

%% ===================================================================== réglages
function parametres(nom)
mws = get_param(nom, 'ModelWorkspace');
code = mws.MATLABCode;
if contains(code, 'T_perception')
    return
end
ajout = {
''
'%% Perception : des mesures à l''état du banc'
'T_perception = T_bno;        % s, période de calcul : celle du BNO055'
'tau_desequilibre = 2;        % s, constante de temps du filtre du couple extérieur et du déséquilibre'
};
mws.MATLABCode = [code newline strjoin(ajout, newline)];
mws.reload;
end

%% ===================================================================== bruit du quaternion (jumeau Simscape)
function bruit_quaternion(s)
if ~isempty(find_system(s, 'SearchDepth', 1, 'Name', 'Bruit quat'))
    return
end
q = 'Quaternion (pas de 2^-14)';
delete_line(s, 'Fusion BNO055/3', [q '/1']);
ajouter(s, 'simulink/Sources/Random Number', 'Bruit quat', [400 305 440 335], 'Mean', '[0; 0; 0]', ...
    'Variance', '(bruit_bno * sigma_angle_deg * pi/180)^2', 'Seed', '[41 42 43]', 'SampleTime', 'T_bno');
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', '+ bruit quat', [470 250 540 300]);
script_fonction(fn, {
'function qb = bruit(q, n)'
'% Bruit de mesure de l''orientation : une petite rotation n (rad, axes du capteur), de même écart type que celui des'
'% angles d''Euler. Le BNO055 tire ses angles d''Euler de son quaternion : les deux portent le même bruit, seul leur pas diffère.'
'd = [1; n(:) / 2];'
'qb = [q(1)*d(1) - q(2:4).''*d(2:4); q(1)*d(2:4) + d(1)*q(2:4) + cross(q(2:4), d(2:4))];'
'qb = qb / norm(qb);'
'if qb(1) < 0, qb = -qb; end'
}, {});
relier(s, 'Fusion BNO055/3', '+ bruit quat/1');
relier(s, 'Bruit quat/1', '+ bruit quat/2');
relier(s, '+ bruit quat/1', [q '/1']);
end

%% ===================================================================== interface sensorielle : le quaternion rejoint les mesures
function interface(s)
if ~isempty(find_system(s, 'SearchDepth', 1, 'Name', 'Quaternion'))
    return
end
set_param([s '/Registres lus'], 'OutputSignals', 'BNO055.euler,BNO055.gyro,vitesses_roues,BNO055.quat');
set_param([s '/Mesures'], 'Inputs', '4');
ajouter(s, 'simulink/Signal Attributes/Signal Conversion', 'Quaternion', [220 140 290 160]);
relier(s, 'Registres lus/4', 'Quaternion/1');
relier(s, 'Quaternion/1', 'Mesures/4', 'quaternion');
set_param([s '/Mesures'], 'Description', ['angles_deg = [roulis; tangage] (°, angles d''Euler), gyro_dps (°/s, axes du capteur), ' ...
    'vitesses_roues (rad/s, sans signe), quaternion [w; x; y; z] (orientation du capteur).']);
note(s, [30 290], {'Quaternion : l''orientation du capteur, au pas de 2^-14. La Perception en tire des angles 8 fois plus fins que les angles d''Euler.'});
end

%% ===================================================================== perception
function perception(s)
if isempty(find_system(s, 'SearchDepth', 1, 'BlockType', 'Inport', 'Name', 'commande appliquée (µs)'))
    add_block('simulink/Ports & Subsystems/In1', [s '/commande appliquée (µs)']);
end
vider(s);
set_param([s '/mesures'], 'Position', [30 113 60 127]);
set_param([s '/commande appliquée (µs)'], 'Position', [30 263 60 277]);
set_param([s '/état'], 'Position', [1110 333 1140 347]);

ajouter(s, 'simulink/Signal Routing/Bus Selector', 'Mesures', [120 60 125 180], 'OutputSignals', 'quaternion,gyro_dps,vitesses_roues', 'ShowName', 'off');
relier(s, 'mesures/1', 'Mesures/1');

% inclinaison
g = sous_systeme(s, 'Inclinaison x2', [260 50 520 140]);
inclinaison(g);
relier(s, 'Mesures/1', 'Inclinaison x2/1');
relier(s, 'Mesures/2', 'Inclinaison x2/2');
vers(s, 'Inclinaison x2/1', 'angles', [600 58 700 82]);
vers(s, 'Inclinaison x2/2', 'vitesses', [600 98 700 122]);

% roues
g = sous_systeme(s, 'Vitesses des roues x4', [260 200 520 290]);
roues(g);
relier(s, 'Mesures/3', 'Vitesses des roues x4/1');
relier(s, 'commande appliquée (µs)/1', 'Vitesses des roues x4/2');
vers(s, 'Vitesses des roues x4/1', 'vitesses_roues', [600 218 700 242]);
vers(s, 'Vitesses des roues x4/2', 'roues_vues', [600 248 700 272]);

g = sous_systeme(s, 'Moment cinétique des roues x2', [260 350 520 410]);
moment(g);
depuis(s, 'vitesses_roues', [120 368 220 392], 'Moment cinétique des roues x2/1');
vers(s, 'Moment cinétique des roues x2/1', 'moment_roues', [600 368 700 392]);

g = sous_systeme(s, 'Couple extérieur et déséquilibre x2', [260 460 520 540]);
desequilibre(g);
depuis(s, 'moment_roues', [120 488 220 512], 'Couple extérieur et déséquilibre x2/1');
vers(s, 'Couple extérieur et déséquilibre x2/1', 'couple_exterieur', [600 473 700 497]);
vers(s, 'Couple extérieur et déséquilibre x2/2', 'desequilibre_mm', [600 503 700 527]);

g = sous_systeme(s, 'Réserve des roues', [260 600 520 660]);
reserve(g);
depuis(s, 'vitesses_roues', [120 618 220 642], 'Réserve des roues/1');
vers(s, 'Réserve des roues/1', 'reserve_roues', [600 618 700 642]);

% état
champs = {'angles', 'vitesses', 'angles_deg', 'vitesses_roues', 'roues_vues', 'moment_roues', 'couple_exterieur', 'desequilibre_mm', 'reserve_roues'};
n = numel(champs);
bc = ajouter(s, 'simulink/Signal Routing/Bus Creator', 'État', [1000 40 1005 640], 'Inputs', num2str(n), 'ShowName', 'off');
for k = 1:n
    y = round(40 + (k - 0.5) * 600 / n);
    if strcmp(champs{k}, 'angles_deg')
        b = depuis(s, 'angles', [780 y - 12 840 y + 12], []);
        ajouter(s, 'simulink/Math Operations/Gain', 'en degrés', [880 y - 15 930 y + 15], 'Gain', '180/pi');
        relier(s, [b '/1'], 'en degrés/1');
        relier(s, 'en degrés/1', sprintf('État/%d', k), 'angles_deg');
    else
        b = depuis(s, champs{k}, [860 y - 12 950 y + 12], []);
        relier(s, [b '/1'], sprintf('État/%d', k), champs{k});
    end
end
relier(s, 'État/1', 'état/1');
set_param(bc, 'Description', ['angles (rad) et angles_deg (°) : [roulis ; tangage] du cardan ; vitesses (rad/s) ; vitesses_roues (rad/s, avec signe) ; ' ...
    'roues_vues (0 ou 1) ; moment_roues (N.m.s, sur [roulis ; tangage]) ; couple_exterieur (N.m) ; desequilibre_mm : position du centre ' ...
    'de masse par rapport au pivot, [selon X ; selon Y] ; reserve_roues (0 à 1).']);
note(s, [30 700], {'Perception : des mesures du banc à son état. Elle n''utilise que ce que l''ESP32 lit (BNO055, TCRT5000) et les impulsions envoyées aux ESC.', ...
    'Inclinaison : angles du cardan tirés du quaternion du BNO055 (pas 8 fois plus fin que les angles d''Euler, exacts en inclinaison combinée),', ...
    'vitesses tirées du gyroscope. Roues : vitesse avec son signe, et visibilité par le capteur. Moment cinétique des roues, couple extérieur', ...
    'qu''elles absorbent, déséquilibre du banc (position du centre de masse par rapport au pivot, en mm) et réserve des roues.', ...
    'Les observateurs CFO sont dans les commandes, comme dans le TP2 : la Perception leur donne des mesures propres.'});
set_param(s, 'Description', 'Perception : des mesures du banc (BNO055, TCRT5000, impulsions envoyées) à son état.');
end

function inclinaison(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'quaternion', [30 53 60 67]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'gyroscope (° par s)', [30 173 60 187]);
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture du quaternion', [120 45 170 75], 'SampleTime', 'T_perception');
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture du gyroscope', [120 165 170 195], 'SampleTime', 'T_perception');
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Angles du cardan (quaternion)', [260 30 440 90]);
script_fonction(fn, {
'function angles = angles_cardan(q, R_montage_bno)'
'% Angles de roulis et de tangage du cardan (rad), tirés du quaternion q = [w; x; y; z] du BNO055 (orientation du capteur'
'% dans le repère fixe). On en tire la verticale vue par le capteur, puis vue par le dispositif (R_montage_bno). Le cardan'
'% tourne en roulis (axe X), puis en tangage (axe Y) : la verticale vue par le dispositif vaut'
'% [-cos(roulis) sin(tangage) ; sin(roulis) ; cos(roulis) cos(tangage)]. Le cap du capteur n''intervient pas.'
'angles = zeros(2, 1);'
'nq = norm(q);'
'if nq < 0.5, return, end                       % pas encore de mesure'
'q = q(:) / nq;'
'w = q(1); x = q(2); y = q(3); z = q(4);'
'v = R_montage_bno * [2*(x*z - w*y); 2*(y*z + w*x); 1 - 2*(x^2 + y^2)];'
'angles = [atan2(v(2), sqrt(v(1)^2 + v(3)^2)); atan2(-v(1), v(3))];'
}, {'R_montage_bno'});
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Vitesses du cardan (gyroscope)', [260 150 440 210]);
script_fonction(fn, {
'function vitesses = vitesses_cardan(gyro_dps, angles, R_montage_bno)'
'% Vitesses de roulis et de tangage (rad/s), tirées du gyroscope du BNO055 (axes du capteur, ramenés aux axes du dispositif).'
'% Pour le cardan, la vitesse de rotation vue par le dispositif vaut'
'% [cos(tangage) d(roulis)/dt ; d(tangage)/dt ; sin(tangage) d(roulis)/dt].'
'w = R_montage_bno * gyro_dps(:) * pi/180;'
'c = cos(angles(2)); s = sin(angles(2));'
'vitesses = [c*w(1) + s*w(3); w(2)];'
}, {'R_montage_bno'});
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'angles (rad)', [560 53 590 67]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'vitesses (rad par s)', [560 173 590 187]);
relier(s, 'quaternion/1', 'Lecture du quaternion/1');
relier(s, 'Lecture du quaternion/1', 'Angles du cardan (quaternion)/1');
relier(s, 'gyroscope (° par s)/1', 'Lecture du gyroscope/1');
relier(s, 'Lecture du gyroscope/1', 'Vitesses du cardan (gyroscope)/1');
relier(s, 'Angles du cardan (quaternion)/1', 'angles (rad)/1');
coude(s, 'Angles du cardan (quaternion)/1', 'Vitesses du cardan (gyroscope)/2', 480);
relier(s, 'Vitesses du cardan (gyroscope)/1', 'vitesses (rad par s)/1');
note(s, [30 260], {'Angles du cardan, tirés du quaternion du BNO055 : pas de 2^-14, contre 1/16° pour les angles d''Euler, et exacts quand le', ...
    'roulis et le tangage se combinent (les angles d''Euler du capteur suivent la séquence Z-Y-X, pas celle du cardan).', ...
    'Vitesses de roulis et de tangage, tirées du gyroscope et des angles. Le cap du capteur n''intervient pas.'});
end

function roues(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'vitesse sans signe (rad par s)', [30 53 60 67]);
ajouter(s, 'simulink/Ports & Subsystems/In1', 'commande appliquée (µs)', [30 213 60 227]);
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture des capteurs', [300 45 350 75], 'SampleTime', 'T_perception');
ajouter(s, 'simulink/Math Operations/Product', 'x signe', [640 40 670 120], 'Inputs', '2');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'vitesse avec signe (rad par s)', [760 73 790 87]);
relier(s, 'vitesse sans signe (rad par s)/1', 'Lecture des capteurs/1');
relier(s, 'Lecture des capteurs/1', 'x signe/1');
% tension appliquée, puis modèle de la roue
ajouter(s, 'simulink/Discrete/Zero-Order Hold', 'Lecture de la commande', [100 205 150 235], 'SampleTime', 'T_perception');
ajouter(s, 'simulink/Math Operations/Bias', '- neutre', [180 205 230 235], 'Bias', '-imp_neutre');
ajouter(s, 'simulink/Math Operations/Gain', 'Sens de rotation', [260 205 320 235], 'Gain', 'sens_moteurs(:)');
ajouter(s, 'simulink/Math Operations/Gain', 'µs vers volts', [350 205 410 235], 'Gain', 'V_alim/(imp_max - imp_neutre)');
ajouter(s, 'simulink/Math Operations/Gain', 'a0', [440 205 500 235], 'Gain', 'a0_roue(:)');
ajouter(s, 'simulink/Math Operations/Gain', 'a1', [440 265 500 295], 'Gain', 'a1_roue(:)');
ajouter(s, 'simulink/Math Operations/Sum', 'Modèle de la roue', [540 205 560 295], 'Inputs', '+-', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Discrete/Discrete-Time Integrator', 'omega du modèle', [610 235 650 265], 'IntegratorMethod', 'Integration: Forward Euler', ...
    'gainval', '1', 'InitialCondition', '0', 'SampleTime', 'T_perception');
relier(s, 'commande appliquée (µs)/1', 'Lecture de la commande/1');
relier(s, 'Lecture de la commande/1', '- neutre/1');
relier(s, '- neutre/1', 'Sens de rotation/1');
relier(s, 'Sens de rotation/1', 'µs vers volts/1');
relier(s, 'µs vers volts/1', 'a0/1');
relier(s, 'a0/1', 'Modèle de la roue/1');
depuis(s, 'omega_modele', [340 268 420 292], 'a1/1');
relier(s, 'a1/1', 'Modèle de la roue/2');
relier(s, 'Modèle de la roue/1', 'omega du modèle/1');
vers(s, 'omega du modèle/1', 'omega_modele', [700 238 790 262]);
% signe et visibilité
f = depuis(s, 'omega_modele', [440 88 520 112], []);
ajouter(s, 'simulink/Math Operations/Sign', 'Signe', [560 85 590 115]);
relier(s, [f '/1'], 'Signe/1');
relier(s, 'Signe/1', 'x signe/2');
relier(s, 'x signe/1', 'vitesse avec signe (rad par s)/1');
f = depuis(s, 'omega_modele', [440 148 520 172], []);
ajouter(s, 'simulink/Math Operations/Abs', 'Valeur absolue', [560 145 590 175]);
ajouter(s, 'simulink/Logic and Bit Operations/Compare To Constant', 'Au-dessus de w_aveugle', [620 145 690 175], ...
    'relop', '>=', 'const', 'w_aveugle', 'OutDataTypeStr', 'boolean');
ajouter(s, 'simulink/Signal Attributes/Data Type Conversion', 'en nombre (0 ou 1)', [720 145 780 175], 'OutDataTypeStr', 'double');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'la roue est vue (0 ou 1)', [840 153 870 167]);
relier(s, [f '/1'], 'Valeur absolue/1');
relier(s, 'Valeur absolue/1', 'Au-dessus de w_aveugle/1');
relier(s, 'Au-dessus de w_aveugle/1', 'en nombre (0 ou 1)/1');
relier(s, 'en nombre (0 ou 1)/1', 'la roue est vue (0 ou 1)/1');
note(s, [30 350], {'Le TCRT5000 voit passer 4 rayons par tour : il mesure la vitesse sans son signe, et mal à basse vitesse.', ...
    'Le signe vient d''un modèle de chaque roue, calculé avec la tension appliquée, tirée des impulsions envoyées aux ESC :', ...
    'd(omega du modèle)/dt = -a1 omega du modèle + a0 V. Ce modèle ne reçoit pas la mesure : une erreur de signe ne peut pas s''entretenir.', ...
    'La roue est vue quand le modèle dépasse w_aveugle. En dessous, la commande bas niveau ne se corrige plus sur la mesure.'});
end

function moment(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'vitesses des roues (rad par s)', [30 63 60 77]);
ajouter(s, 'simulink/Math Operations/Gain', 'J cos 45° [sx ; sy]', [160 55 280 85], 'Gain', 'J_roue*cosd(45)*[sx_roues; sy_roues]', 'Multiplication', 'Matrix(K*u)');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'moment cinétique (N.m.s)', [360 63 390 77]);
relier(s, 'vitesses des roues (rad par s)/1', 'J cos 45° [sx ; sy]/1');
relier(s, 'J cos 45° [sx ; sy]/1', 'moment cinétique (N.m.s)/1');
note(s, [30 140], {'Moment cinétique des 4 roues par rapport au dispositif, sur [roulis ; tangage] : H = J cos 45° [somme sx w ; somme sy w].', ...
    'À la vitesse de repos, les 4 roues s''annulent deux à deux : H = 0.'});
end

function desequilibre(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'moment cinétique (N.m.s)', [30 63 60 77]);
ajouter(s, 'simulink/Math Operations/Sum', 'H - H filtré', [140 55 160 115], 'Inputs', '+-', 'IconShape', 'rectangular');
ajouter(s, 'simulink/Math Operations/Gain', '1 sur tau', [220 70 280 100], 'Gain', '1/tau_desequilibre');
ajouter(s, 'simulink/Discrete/Discrete-Time Integrator', 'H filtré', [360 140 400 170], 'IntegratorMethod', 'Integration: Forward Euler', ...
    'gainval', '1', 'InitialCondition', '0', 'SampleTime', 'T_perception');
ajouter(s, 'simulink/Math Operations/Gain', 'vers le centre de masse', [480 170 560 200], 'Gain', '1000/max(g, 0.01)*[0 1/m_disp; -1/(m_disp + m_croix) 0]', 'Multiplication', 'Matrix(K*u)');
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'couple extérieur (N.m)', [640 78 670 92]);
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'déséquilibre (mm)', [640 178 670 192]);
relier(s, 'moment cinétique (N.m.s)/1', 'H - H filtré/1');
relier(s, 'H - H filtré/1', '1 sur tau/1');
relier(s, '1 sur tau/1', 'couple extérieur (N.m)/1');
coude(s, '1 sur tau/1', 'H filtré/1', 320);
relier(s, 'H filtré/1', 'H - H filtré/2');
coude(s, '1 sur tau/1', 'vers le centre de masse/1', 440);
relier(s, 'vers le centre de masse/1', 'déséquilibre (mm)/1');
note(s, [30 260], {'Couple extérieur sur le dispositif (pesanteur, poussées), sur [roulis ; tangage] : quand le dispositif est immobile, c''est le couple que', ...
    'les roues absorbent, la dérivée de leur moment cinétique. Il est filtré par un premier ordre de constante de temps tau_desequilibre.', ...
    'Déséquilibre : le couple de pesanteur vaut m g fois le décalage horizontal du centre de masse. On en tire la position du centre de', ...
    'masse par rapport au pivot, en mm, [selon X ; selon Y] : x = couple de tangage / (m g), y = -couple de roulis / (m g).', ...
    'C''est le réglage à reporter sur les écrous d''équilibrage. Juste pendant que le dispositif est immobile.'});
end

function reserve(s)
ajouter(s, 'simulink/Ports & Subsystems/In1', 'vitesses des roues (rad par s)', [30 63 60 77]);
fn = ajouter(s, 'simulink/User-Defined Functions/MATLAB Function', 'Marge aux limites', [140 40 320 100]);
script_fonction(fn, {
'function r = marge(w, w_roue_min, w_roue_max, w_repos)'
'% Réserve des roues, de 0 à 1 : 1 quand les 4 roues sont à leur vitesse de repos, 0 quand l''une d''elles atteint une'
'% limite de vitesse. C''est la part du moment cinétique que les roues peuvent encore absorber.'
'm = min(min(w(:) - w_roue_min), min(w_roue_max - w(:)));'
'r = max(0, min(1, m / max(min(w_repos - w_roue_min, w_roue_max - w_repos), 1)));'
}, {'w_roue_min', 'w_roue_max', 'w_repos'});
ajouter(s, 'simulink/Ports & Subsystems/Out1', 'réserve (0 à 1)', [400 63 430 77]);
relier(s, 'vitesses des roues (rad par s)/1', 'Marge aux limites/1');
relier(s, 'Marge aux limites/1', 'réserve (0 à 1)/1');
end

%% ===================================================================== niveau haut
function niveau_haut(nom)
ph = get_param([nom '/Perception'], 'PortHandles');
if get_param(ph.Inport(2), 'Line') == -1
    if isempty(find_system(nom, 'SearchDepth', 1, 'BlockType', 'Goto', 'GotoTag', 'imp'))
        p = get_param([nom '/Pupitre'], 'Position');
        vers(nom, 'Pupitre/1', 'imp', [p(3) + 10 p(4) + 15 p(3) + 60 p(4) + 35]);
    end
    c = get_param(ph.Inport(2), 'Position');
    depuis(nom, 'imp', [c(1) - 70 c(2) - 10 c(1) - 20 c(2) + 10], 'Perception/2');
end
configurer_scope([nom '/Roues'], {'vitesse des roues, avec signe (perception, rad/s)', 'vitesse réelle des roues (rad/s)', 'courant des moteurs (A)'});
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

function coude(s, src, dst, x)
c = strsplit(src, '/'); ph = get_param([s '/' strjoin(c(1:end - 1), '/')], 'PortHandles'); ps = ph.Outport(str2double(c{end}));
c = strsplit(dst, '/'); ph = get_param([s '/' strjoin(c(1:end - 1), '/')], 'PortHandles'); pd = ph.Inport(str2double(c{end}));
a = get_param(ps, 'Position'); b = get_param(pd, 'Position');
pts = [x a(2); x b(2); b];
if get_param(ps, 'Line') == -1, pts = [a; pts]; end
l = add_line(s, pts);
if get_param(pd, 'Line') == -1 || get_param(get_param(pd, 'Line'), 'SrcPortHandle') ~= ps
    delete_line(l);
    add_line(s, src, dst, 'autorouting', 'smart');
end
end

function vider(s)
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

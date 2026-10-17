function P = params_monowheel(config)
%PARAMS_MONOWHEEL Paramètres et gains du modèle de stabilisation par roues de réaction.
%
%   P = params_monowheel('robot_final')  robot de 6,5 kg, 4 moteurs Eaglepower 8308-160KV
%   P = params_monowheel('robot_A2212')  même robot avec les 4 moteurs A2212 achetés (démonstration d'échec)
%   P = params_monowheel('banc_1axe')    banc de la phase 1 du plan TRL4 : pendule léger, 1 moteur A2212
%
%   Conventions
%   - Angles du corps : Theta = [phi ; theta] (roulis, tangage), en rad.
%   - Roue i : axe a_i dans le plan horizontal, B = [a_1 a_2 a_3 a_4] (2 x 4).
%   - Couple du moteur i sur sa roue : tau_i. Le corps reçoit -B*tau.
%   - Vitesses des roues mesurées par rapport au corps : w (4 x 1), en rad/s.
%
%   Les valeurs marquées (H) sont des hypothèses à mesurer sur le matériel.

if nargin < 1, config = 'robot_final'; end
P.config = config;

%% --- Géométrie des roues et choix de la configuration ---
c = cos(pi/4);
switch config
    case {'robot_final', 'robot_A2212'}
        % Robot complet : 6,5 kg, hauteur 50 cm, rayon 20 cm (note de dimensionnement)
        m = 6.5; H = 0.50; R = 0.20; h = 0.25;
        Icm = m * (3 * R^2 + H^2) / 12;          % inertie au centre de masse (cylindre plein)
        corps.Jp = Icm + m * h^2;                % inertie autour du point de contact au sol
        corps.m = m; corps.h = h;
        corps.actif = [1; 1];                    % roulis et tangage libres
        B = c * [1 -1 -1 1; 1 1 -1 -1];          % 4 roues à 45 degrés
        if strcmp(config, 'robot_final'), mot = moteur_eaglepower(); else, mot = moteur_a2212(); end
        scen.Theta0 = deg2rad([5; -3]);          % inclinaison initiale
        scen.pert = [3.0 0.10 1.0  6.0 0.10 1.0]; % [t1 durée1 couple1(roulis)  t2 durée2 couple2(tangage)], N.m
        lqr_w = struct('phi', deg2rad(3), 'dphi', 0.5, 'W', 0.6 * mot.wmax, 'v', 3.0);
        pp_poles = [-6 -9 -0.8];                 % pôles en boucle fermée (par axe)
    case 'banc_1axe'
        % Pendule à un axe, une seule roue alignée avec le roulis (phase 1 du plan TRL4)
        corps.m = 0.25;                          % (H) support + moteur + disque
        corps.h = 0.08;                          % (H) distance pivot - centre de masse
        corps.Jp = 0.0025;                       % (H) inertie autour du pivot
        corps.actif = [1; 0];                    % tangage bloqué par le pivot
        B = [1 0 0 0; 0 0 0 0];                  % seule la roue 1 travaille
        mot = moteur_a2212();
        scen.Theta0 = deg2rad([5; 0]);
        scen.pert = [3.0 0.10 0.02  6.0 0.10 0];
        lqr_w = struct('phi', deg2rad(3), 'dphi', 1.0, 'W', 0.5 * mot.wmax, 'v', 0.08);
        pp_poles = [-14 -20 -1.5];
    otherwise
        error('Configuration inconnue : %s', config);
end
corps.g = 9.81;
corps.mgh = corps.m * corps.g * corps.h;

P.corps = corps;
P.B = B;
P.Bpinv = pinv(B);                               % allocation de norme minimale
P.BBt = diag(B * B');                            % 2 pour le robot, [1 ; 0] pour le banc

%% --- Boucle moteur (comme le TP : modèle réduit, commande de vitesse, ESO) ---
%   Modèle réduit (L di/dt = 0) : w' = a0 w + b0 V + d
mot.a0 = -(mot.Kt * mot.Ke / (mot.Jr * mot.R) + mot.f / mot.Jr);
mot.b0 = mot.Kt / (mot.Jr * mot.R);
%   Commande de vitesse : e = w - w*, V = (-Kv e - a0 w - d_est + w*') / b0
%   Observateur ESO : états [w ; d], d' = 0
Aa = [mot.a0 1; 0 0]; Ba = [mot.b0; 0]; Ca = [1 0];
L = place(Aa', Ca', mot.eso_poles)';
mot.L = L;
mot.Aeso = Aa - L * Ca;                          % forme d'état de l'observateur
mot.Beso = [L Ba];                               % entrée [w ; V]
mot.tau_max = mot.Kt * mot.Imax;
P.mot = mot;

%% --- Commande haute : retour d'état par axe, états [angle ; vitesse ; W] ---
%   W = B*w : vitesse projetée des roues sur l'axe.
%   angle'' = (mgh/Jp) angle - v/Jp      (v = B*tau : couple de réaction demandé)
%   W'      = v/Jr - BBt * angle''
P.v_max = sum(abs(B), 2) * mot.tau_max;          % couple maximal par axe
K_lqr = zeros(2, 3); K_pp = zeros(2, 3); P.axe = cell(2, 1);
for k = 1:2
    if ~corps.actif(k), continue; end
    a = corps.mgh / corps.Jp;
    A = [0 1 0; a 0 0; -P.BBt(k) * a 0 0];
    Bv = [0; -1 / corps.Jp; 1 / mot.Jr + P.BBt(k) / corps.Jp];
    Q = diag(1 ./ [lqr_w.phi lqr_w.dphi lqr_w.W].^2);
    Rr = 1 / lqr_w.v^2;
    K_lqr(k, :) = lqr(A, Bv, Q, Rr);
    K_pp(k, :) = place(A, Bv, pp_poles);
    P.axe{k} = struct('A', A, 'B', Bv, 'poles_bo', eig(A), ...
        'poles_lqr', eig(A - Bv * K_lqr(k, :)), 'poles_pp', eig(A - Bv * K_pp(k, :)));
end
% Mise en forme pour le vecteur d'état z = [phi ; theta ; phi' ; theta' ; Wx ; Wy]
P.K_lqr = etale(K_lqr);
P.K_pp = etale(K_pp);
P.lqr_w = lqr_w;
P.pp_poles = pp_poles;

%% --- IMU (BNO055 en mode fusion) ---
P.imu.Ts = 0.01;                                 % 100 Hz
P.imu.sig_angle = deg2rad(0.1);                  % bruit sur l'angle
P.imu.sig_gyro = deg2rad(0.1);                   % bruit sur la vitesse angulaire
P.imu.biais_angle = deg2rad([0.2; -0.2]);        % (H) erreur de verticale
P.imu.graine = [11 12 21 22];

%% --- Scénario ---
scen.Tf = 10;
scen.angle_chute = deg2rad(40);                  % arrêt de la simulation : le robot est tombé
P.scen = scen;
P.ctrl_mode = 1;                                 % 1 = LQR, 2 = placement de pôles
end

function Kz = etale(K)
% Passe de [k_angle k_vitesse k_W] par axe au vecteur z = [phi theta phi' theta' Wx Wy]
Kz = zeros(2, 6);
for k = 1:2
    Kz(k, [k, 2 + k, 4 + k]) = K(k, :);
end
end

function mot = moteur_eaglepower()
% Eaglepower 8308-160KV (dimensionnement du 07/11/2025), volant 0,25 kg, r = 80 mm
mot.nom = 'Eaglepower 8308-160KV';
mot.KV = 160;
mot.Kt = 60 / (2 * pi * mot.KV);                 % 0,0597 N.m/A
mot.Ke = mot.Kt;
mot.R = 0.10;                                    % (H) résistance de phase équivalente
mot.Jw = 0.25 * 0.08^2;                          % volant à jante : m r^2 = 0,0016 kg.m2
mot.Jr = mot.Jw + 1.2e-4;                        % (H) + inertie du rotor
mot.f = 1e-5;                                    % (H) frottement visqueux
mot.Vmax = 22.2;                                 % LiPo 6S
mot.Imax = 48;                                   % courant maximal (note de dimensionnement)
mot.wmax = mot.KV * mot.Vmax * 2 * pi / 60;
mot.Kv = 40;                                     % pôle de la boucle de vitesse
mot.eso_poles = [-150 -200];
end

function mot = moteur_a2212()
% A2212 930KV (fiche fabricant : 9,8 A en continu sous 11,1 V), disque PLA de 30 g, r = 60 mm
mot.nom = 'A2212 930KV';
mot.KV = 930;
mot.Kt = 60 / (2 * pi * mot.KV);                 % 0,0103 N.m/A
mot.Ke = mot.Kt;
mot.R = 0.10;                                    % (H)
mot.Jw = 0.8 * 0.030 * 0.060^2;                  % disque à jante et rayons : environ 0,8 m r^2
mot.Jr = mot.Jw + 1.5e-5;                        % (H) + inertie du rotor
mot.f = 2e-6;                                    % (H)
mot.Vmax = 11.1;                                 % LiPo 3S
mot.Imax = 9.8;
mot.wmax = mot.KV * mot.Vmax * 2 * pi / 60;
mot.Kv = 40;
mot.eso_poles = [-150 -200];
end

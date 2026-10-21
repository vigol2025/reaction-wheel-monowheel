%% Banc moteur A2212 : paramètres
% Commande du TP1 (M. Larbi) sur le vrai moteur de la maquette, à travers l'ESP32.
% Lancer ce script, puis banc_moteur_A2212.slx (bouton Run).
% (F) fiche technique, (C) calculé, (M) mesuré sur la CAO, (E) estimé sur photo, (H) hypothèse

%% Liaison avec l'ESP32

port_esp32 = "COM3"                % port série de l'ESP32 (Gestionnaire de périphériques > Ports COM)
Ts_com = 0.01                      % s, une trame envoyée et une reçue toutes les 10 ms (100 Hz)

%% Paramètres du moteur

Vbat = 11.1                        % V, batterie 3S (F)
KV = 1400                          % tr/min/V (F)
Rm = 0.08                          % ohm, entre deux fils du moteur (H)
Lm = 30e-6                         % H, entre deux fils du moteur (H)
Ke = 60/(2*pi*KV)                  % V.s/rad (C)
Kt = Ke                            % N.m/A (C)
fv = 5e-6                          % N.m.s/rad (H)

%% Inertie de la partie tournante

J_rotor = 5e-6                     % kg.m2, cloche et aimants (H)
J_disque = 0.9*6.67e-5             % kg.m2, disque PLA du STL, 0,9 pour le remplissage (M, E)
J_vis = 4*0.008*0.055^2            % kg.m2, 4 vis M6 x 20 acier + écrous, 8 g chacune, à 55 mm (E, M)
Jm = J_rotor + J_disque + J_vis    % kg.m2

%% Modèle réduit

a0 = -(Kt*Ke/(Jm*Rm) + fv/Jm)      % s-1
b0 = Kt/(Jm*Rm)                    % rad/s2 par V

%% Commande

K = 8                              % s-1

%% Observateur ESO

Aa = [a0 1; 0 0]
Ba = [b0; 0]
Ca = [1 0]
p0 = [-20 -24]
L = place(Aa', Ca', p0)'
A_eso = Aa - L*Ca
B_eso = [Ba L]
eso_actif = 1

%% ESC et limites du banc

imp_neutre = 1500                  % µs, 1500 µs = arrêt
imp_course = 500                   % µs
Vmax = Vbat                        % V, saturation de tension de la commande
imp_banc_min = 1300                % µs, limites du banc (disque en PLA), les mêmes que dans le firmware
imp_banc_max = 1700                % µs

%% Référence

w_moy = 300                        % rad/s
w_amp = 100                        % rad/s
w_puls = 0.5                       % rad/s, wr = 300 + 100 sin(0,5 t)

%% Jumeau numérique : perturbation et bruit simulés (coupés sur le banc)

tau_L = 0.03                       % N.m
t_pert = 3                         % s
perturbation_active = 0
sigma_bruit = 2                    % rad/s
Ts_bruit = 0.005                   % s
bruit_actif = 0

%% Application du port série au modèle

mdl = 'banc_moteur_A2212';
if ~bdIsLoaded(mdl)
    load_system(fullfile(fileparts(mfilename('fullpath')), [mdl '.slx']));
end
if strcmp(get_param(mdl, 'SimulationStatus'), 'stopped')
    for bloc = ["Configuration série", "Envoi série", "Réception série"]
        set_param(mdl + "/Liaison ESP32/" + bloc, 'Port', port_esp32);
    end
end

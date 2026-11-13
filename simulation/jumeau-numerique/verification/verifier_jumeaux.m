% Contrôle des deux jumeaux numériques du banc de stabilisation (version 3).
% Chaque essai est joué sur le jumeau Simscape puis sur le jumeau Webots, avec les mêmes réglages, et comparé au calcul.
% Avant de lancer : ouvrir webots/worlds/banc_stabilisation.wbt dans Webots (message « jumeau Webots prêt »).
% Le modèle n'est jamais enregistré : les réglages des essais sont perdus à la fermeture.
% Usage : verifier_jumeaux            (les deux jumeaux)
%         verifier_jumeaux Simscape   (un seul)
function verifier_jumeaux(varargin)
ici = fileparts(mfilename('fullpath'));
dossier = fileparts(ici);
nom = 'jumeau_banc_rw';
if nargin > 0, variantes = varargin; else, variantes = {'Simscape', 'Webots'}; end
cao = jsondecode(fileread(fullfile(dossier, 'construction', 'cao_jumeau.json')));
J = cao.controle.J_roue; deg = 180/pi; c45 = cosd(45); sx = [1 -1 -1 1];
if bdIsLoaded(nom), close_system(nom, 0); end
load_system(fullfile(dossier, [nom '.slx']));
set_param(nom, 'SimMechanicsOpenEditorOnUpdate', 'off', 'EnablePacing', 'off');
set_param([nom '/Pupitre/Mode : manuel (haut) ou commande (bas)'], 'sw', '1');   % essais du procédé : pilotage manuel des ESC
mws = get_param(nom, 'ModelWorkspace'); code0 = mws.MATLABCode;
pilotage_banc('scenario', zeros(1, 7));   % pendant les essais, le manche de l'interface de pilotage ne joue pas
fermer = onCleanup(@() fin(nom));
R = struct();

for v = 1:numel(variantes)
    var = variantes{v};
    set_param([nom '/Procédé'], 'LabelModeActiveChoice', var);
    fprintf('\n=================== jumeau %s\n', var);

    %% 1. Chute libre en roulis (tangage bloqué, roues libres) : pendule inversé
    for pv = [24 -8]
        r = essai(nom, code0, {'pivot_mm', num2str(pv); 'blocage_tangage', '1'; 'angle0_roulis_deg', '2'; 'bruit_bno', '0'; ...
            'R_moteur', '1e6'; 'f_roue', '0'; 'b_cardan', '0'}, 0.6);
        [M, G, I] = ensemble(cao, pv);
        Ieff = I(1, 1) - 2 * J;                             % roues libres : leur rotation propre ne suit pas le corps
        p = sqrt(M * 9.81 * hypot(G(3), G(2)) / Ieff); eq = atan(G(2) / G(3));
        th = (eq + (2 / deg - eq) * cosh(p * r.t)) * deg;
        k = abs(r.angles(:, 1)) < 8;
        fprintf('1. chute libre, pivot %+3d : h = %5.2f mm, p = %.3f rad/s ; écart au pendule jusqu''à 8° : %.4f° ; tangage bloqué : %.1e°\n', ...
            pv, G(3) * 1000, p, max(abs(r.angles(k, 1) - th(k))), max(abs(r.angles(:, 2))));
        R.(var).(sprintf('chute%d', abs(pv))) = r; R.pendule.(sprintf('chute%d', abs(pv))) = [r.t th];
    end

    %% 2. Démarrage d'une roue (deux axes bloqués) : ESC 1 à 1600 µs à 1,5 s
    r = essai(nom, code0, {'blocage_roulis', '1'; 'blocage_tangage', '1'; 'bruit_bno', '0'; 'essai_t', '1.5'; 'essai_echelon_us', '[100 0 0 0]'}, 3.5);
    mw = get_param(nom, 'ModelWorkspace');
    Ke = mw.getVariable('Ke'); Rm = mw.getVariable('R_moteur'); f0 = mw.getVariable('f_roue'); V = 0.2 * mw.getVariable('V_alim');
    Wss = Ke * V / (Ke^2 + Rm * f0); tau = J * Rm / (Ke^2 + Rm * f0);
    W1 = r.roues(:, 1);
    t63 = interp1(W1(r.t > 1.5 & W1 < 0.9 * Wss), r.t(r.t > 1.5 & W1 < 0.9 * Wss), 0.632 * Wss);
    fprintf('2. roue 1 à 1600 µs : %.1f rad/s en fin (calcul %.1f), constante de temps %.3f s (calcul %.3f + retard de trame), courant max %.1f A\n', ...
        W1(end), Wss, t63 - 1.5, tau, max(r.courants(:, 1)));
    k = r.tm > 2.5;
    fprintf('   TCRT5000 : écart à la vitesse réelle en régime %.2f rad/s au plus ; courant d''alimentation %.2f A ; axes bloqués %.1e°\n', ...
        max(abs(r.w_mes(k, 1) - interp1(r.t, W1, r.tm(k)))), r.i_alim(end), max(abs(r.angles(:))));
    R.(var).roue = r;

    %% 3. Armement : 1600 µs dès la mise sous tension, l'ESC ne doit pas démarrer
    r = essai(nom, code0, {'blocage_roulis', '1'; 'blocage_tangage', '1'; 'bruit_bno', '0'; 'essai_t', '0'; 'essai_echelon_us', '[100 0 0 0]'}, 2);
    r2 = essai(nom, code0, {'blocage_roulis', '1'; 'blocage_tangage', '1'; 'bruit_bno', '0'; 'essai_t', '0'; 'essai_echelon_us', '[100 0 0 0]'; 'armement_actif', '0'}, 2);
    fprintf('3. 1600 µs dès t = 0 : roue 1 à %.2g rad/s au plus (ESC non armé) ; sans armement : %.0f rad/s à 2 s\n', max(abs(r.roues(:, 1))), r2.roues(end, 1));

    %% 4. Réaction : sans pesanteur, tangage bloqué, la roue 1 accélère et le dispositif part en sens inverse
    r = essai(nom, code0, {'g', '0'; 'blocage_tangage', '1'; 'angle0_roulis_deg', '0'; 'bruit_bno', '0'; 'b_cardan', '0'; ...
        'essai_t', '1.5'; 'essai_echelon_us', '[100 0 0 0]'}, 2.5);
    [~, ~, I] = ensemble(cao, 24);
    dphi = r.vitesses(:, 1) / deg;
    H = (I(1, 1) - 2 * J) * dphi + J * c45 * ((r.roues + dphi * c45 * sx) * sx');
    kb = find(abs(r.angles(:, 1)) > 19, 1); if isempty(kb), kb = numel(r.t); end
    fprintf('4. moment cinétique en roulis : %.2e N.m.s au plus, pour %.2e échangés (%.2f %%) ; butée atteinte à %.3f s\n', ...
        max(abs(H(1:kb - 1))), J * c45 * max(abs(r.roues(1:kb - 1, 1))), 100 * max(abs(H(1:kb - 1))) / (J * c45 * max(abs(r.roues(1:kb - 1, 1)))), r.t(kb));
    R.(var).reaction = r;

    %% 5. BNO055 sans bruit : angles d'Euler et gyroscope comparés au cardan
    r = essai(nom, code0, {'bruit_bno', '0'; 'pivot_mm', '-8'; 'angle0_roulis_deg', '3'; 'angle0_tangage_deg', '-2'}, 1.5);
    q = interp1(r.t, r.angles, r.tm) / deg; dq = interp1(r.t, r.vitesses, r.tm) / deg;
    roulis = atan2(sin(q(:, 1)), cos(q(:, 1)) .* cos(q(:, 2))) * deg; tangage = asin(cos(q(:, 1)) .* sin(q(:, 2))) * deg;
    fprintf('5. BNO055 : écart roulis %.3f°, tangage %.3f° (pas de 0,0625°) ; gyroscope x %.3f, y %.3f °/s ; accéléromètre au départ %s m/s²\n', ...
        max(abs(r.euler(:, 2) - roulis)), max(abs(r.euler(:, 3) - tangage)), max(abs(r.gyro(:, 1) - dq(:, 1) .* cos(q(:, 2)) * deg)), ...
        max(abs(r.gyro(:, 2) - dq(:, 2) * deg)), mat2str(r.acc(1, :), 3));
    R.(var).bno = r;

    %% 6. Essai complet : deux axes libres, pesanteur, la roue 1 démarre à 1,2 s
    r = essai(nom, code0, {'bruit_bno', '0'; 'pivot_mm', '8'; 'angle0_roulis_deg', '0.5'; 'angle0_tangage_deg', '0.5'; 'armement_actif', '0'; ...
        'essai_t', '0.2'; 'essai_echelon_us', '[150 0 0 0]'}, 3);
    fprintf('6. essai complet : roulis %.2f°, tangage %.2f° à 0,5 s ; %.2f°, %.2f° en fin ; durée du calcul %.1f s pour 3 s simulées\n', ...
        interp1(r.t, r.angles(:, 1), 0.5), interp1(r.t, r.angles(:, 2), 0.5), r.angles(end, 1), r.angles(end, 2), r.duree);
    R.(var).complet = r;
end
mws.MATLABCode = code0;

%% Comparaison des deux jumeaux
if all(isfield(R, {'Simscape', 'Webots'}))
    fprintf('\n=================== écart entre les deux jumeaux (Webots moins Simscape)\n');
    n = {'chute24', 'chute libre, pivot +24'; 'chute8', 'chute libre, pivot -8'; 'reaction', 'réaction sans pesanteur'; 'complet', 'essai complet'};
    for k = 1:size(n, 1)
        a = R.Simscape.(n{k, 1}); b = R.Webots.(n{k, 1});
        qa = interp1(a.t, a.angles, b.t);
        libre = (1:numel(b.t))' < find([any(abs(qa) > 15 | abs(b.angles) > 15, 2); true], 1);   % avant les butées
        fprintf('%-26s : angles du cardan %.3f° au plus avant 15°\n', n{k, 2}, max(max(abs(b.angles(libre, :) - qa(libre, :)))));
    end
    a = R.Simscape.roue; b = R.Webots.roue;
    fprintf('%-26s : vitesse %.2f rad/s au plus (%.2f %%), courant %.2f A au plus\n', 'démarrage d''une roue', ...
        max(abs(b.roues(:, 1) - interp1(a.t, a.roues(:, 1), b.t))), 100 * max(abs(b.roues(:, 1) - interp1(a.t, a.roues(:, 1), b.t))) / max(a.roues(:, 1)), ...
        max(abs(b.courants(:, 1) - interp1(a.t, a.courants(:, 1), b.t))));
    a = R.Simscape.bno; b = R.Webots.bno; k = b.tm > 0 & b.tm < 0.25;
    fprintf('%-26s : angles d''Euler %.3f°, gyroscope %.2f °/s, accéléromètre %.3f m/s² au plus (0,01 à 0,25 s)\n', 'BNO055', ...
        max(max(abs(b.euler(k, :) - a.euler(k, :)))), max(max(abs(b.gyro(k, :) - a.gyro(k, :)))), max(max(abs(b.acc(k, :) - a.acc(k, :)))));
    tracer(R, fullfile(ici, 'comparaison_jumeaux.png'));
end
end

%% ------------------------------------------------------------------ outils
function fin(nom)
pilotage_banc('scenario', []);
if bdIsLoaded(nom), close_system(nom, 0); end
end

function r = essai(nom, code0, paires, duree)
% Remet les réglages d'origine, applique ceux de l'essai, simule et range les résultats en colonnes.
mws = get_param(nom, 'ModelWorkspace');
code = code0;
paires = [paires; {'t_lacher', '0'; 'perturbation_couple', '[0 0]'}];   % procédé seul : libre dès le départ, sans poussée
for k = 1:size(paires, 1)
    code = regexprep(code, ['(?m)^' paires{k, 1} ' = [^;]*;'], [paires{k, 1} ' = ' paires{k, 2} ';']);
    assert(~isempty(regexp(code, ['(?m)^' paires{k, 1} ' = ' regexptranslate('escape', paires{k, 2}) ';'], 'once')), paires{k, 1});
end
mws.MATLABCode = code; mws.reload;
out = sim(nom, 'StopTime', num2str(duree));
g = out.logsout.get('grandeurs_reelles').Values; c = out.logsout.get('capteurs').Values;
r.t = g.angles_cardan.Time;
r.angles = col(g.angles_cardan); r.vitesses = col(g.vitesses_cardan); r.roues = col(g.roues_tr_min) * 2 * pi / 60;
r.courants = col(g.courants_A); r.i_alim = col(g.courant_alim_A);
r.tm = c.BNO055.euler.Time;
r.euler = col(c.BNO055.euler); r.gyro = col(c.BNO055.gyro); r.acc = col(c.BNO055.acc); r.w_mes = col(c.vitesses_roues);
r.duree = out.SimulationMetadata.TimingInfo.ExecutionElapsedWallTime;
end

function x = col(ts)
x = squeeze(ts.Data);
if size(x, 1) ~= numel(ts.Time), x = x.'; end
end

function [M, G, I] = ensemble(cao, pivot)
% Masse, centre de masse (par rapport au pivot) et tenseur d'inertie au pivot de tout ce qui tourne en roulis
% (dispositif, roues, paliers, croisillon), calculés depuis les données de la CAO.
M = 0; S = zeros(3, 1); I = zeros(3);
for k = 1:numel(cao.instances)
    in = cao.instances(k); g = in.groupe;
    if strcmp(g, 'bati'), continue, end
    s = cao.solides.(matlab.lang.makeValidName(in.solide));
    R = in.R; t = in.t_mm(:) / 1000;
    if startsWith(g, 'roue')
        a = cao.angles_roues.(sprintf('x%s', g(end)));
        Rk = [cosd(a) -sind(a) 0; sind(a) cosd(a) 0; 0 0 1] * [0 0 1; 0 1 0; -1 0 0];
        R = Rk * R; t = Rk * t;
    end
    if ~any(strcmp(g, {'paliers', 'croisillon'})), t = t - [0; 0; pivot / 1000]; end
    r = R * s.G(:) + t;
    M = M + s.m; S = S + s.m * r;
    I = I + R * s.I * R' + s.m * (r' * r * eye(3) - r * r');
end
G = S / M;
end

function tracer(R, fichier)
f = figure('Visible', 'off', 'Position', [0 0 1300 900]);
try, theme(f, 'light'); catch, end
bleu = [0.12 0.40 0.75]; rouge = [0.85 0.25 0.15];
tiledlayout(f, 2, 3, 'TileSpacing', 'compact', 'Padding', 'compact');
titres = {'chute24', 'Chute libre en roulis, pivot à +24 mm'; 'chute8', 'Chute libre en roulis, pivot à -8 mm'};
for k = 1:2
    nexttile; hold on; grid on
    a = R.Simscape.(titres{k, 1}); b = R.Webots.(titres{k, 1}); p = R.pendule.(titres{k, 1});
    plot(p(:, 1), p(:, 2), 'k:', 'LineWidth', 1.5); plot(a.t, a.angles(:, 1), 'Color', bleu, 'LineWidth', 1.4); plot(b.t, b.angles(:, 1), '--', 'Color', rouge, 'LineWidth', 1.4);
    ylim([0 22]); xlabel('temps (s)'); ylabel('roulis (°)'); title(titres{k, 2});
    legend('pendule (calcul)', 'Simscape', 'Webots', 'Location', 'northwest');
end
nexttile; hold on; grid on
a = R.Simscape.roue; b = R.Webots.roue;
plot(a.t, a.roues(:, 1), 'Color', bleu, 'LineWidth', 1.4); plot(b.t, b.roues(:, 1), '--', 'Color', rouge, 'LineWidth', 1.4);
plot(b.tm, b.w_mes(:, 1), ':', 'Color', [0.2 0.6 0.2], 'LineWidth', 1.2);
xlim([1.4 3]); xlabel('temps (s)'); ylabel('vitesse de la roue 1 (rad/s)'); title('Roue 1 : 1600 µs à 1,5 s, axes bloqués');
legend('Simscape', 'Webots', 'TCRT5000 (Webots)', 'Location', 'southeast');
nexttile; hold on; grid on
a = R.Simscape.reaction; b = R.Webots.reaction;
plot(a.t, a.angles(:, 1), 'Color', bleu, 'LineWidth', 1.4); plot(b.t, b.angles(:, 1), '--', 'Color', rouge, 'LineWidth', 1.4);
xlim([1.4 2.5]); xlabel('temps (s)'); ylabel('roulis (°)'); title('Réaction : roue 1 lancée, sans pesanteur');
legend('Simscape', 'Webots', 'Location', 'southwest');
for j = 1:2
    nexttile; hold on; grid on
    a = R.Simscape.complet; b = R.Webots.complet; noms = {'roulis', 'tangage'};
    plot(a.t, a.angles(:, j), 'Color', bleu, 'LineWidth', 1.4); plot(b.t, b.angles(:, j), '--', 'Color', rouge, 'LineWidth', 1.4);
    plot(b.tm, b.euler(:, j + 1), ':', 'Color', [0.2 0.6 0.2], 'LineWidth', 1.2);
    xlabel('temps (s)'); ylabel([noms{j} ' (°)']); title(['Essai complet : ' noms{j} ', roue 1 à 1650 µs à 0,2 s']);
    legend('Simscape', 'Webots', 'BNO055 (Webots)', 'Location', 'best');
end
exportgraphics(f, fichier, 'Resolution', 130);
close(f);
fprintf('figure : %s\n', fichier);
end

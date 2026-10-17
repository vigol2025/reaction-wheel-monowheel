function R = run_monowheel(configs, modes)
%RUN_MONOWHEEL Simule le modèle monowheel_rw et trace les résultats.
%
%   run_monowheel                          les 3 configurations, LQR et placement de pôles
%   run_monowheel({'banc_1axe'}, 1)        une configuration, LQR seul
%
%   Les figures sont enregistrées dans resultats/ et un tableau récapitulatif est affiché.

if nargin < 1, configs = {'robot_final', 'robot_A2212', 'banc_1axe'}; end
if nargin < 2, modes = [1 2]; end
here = fileparts(mfilename('fullpath'));
mdl = 'monowheel_rw';
if ~exist(fullfile(here, [mdl '.slx']), 'file'), build_monowheel_model; end
load_system(fullfile(here, [mdl '.slx']));
outdir = fullfile(here, 'resultats');
if ~exist(outdir, 'dir'), mkdir(outdir); end
noms_lois = {'LQR', 'placement de pôles'};
suffixes = {'lqr', 'placement-poles'};

R = struct([]);
for c = 1:numel(configs)
    for mo = modes
        P = params_monowheel(configs{c});
        P.ctrl_mode = mo;
        assignin('base', 'P', P);
        out = sim(mdl);
        r = indicateurs(out, P);
        r.config = configs{c}; r.loi = noms_lois{mo};
        R = [R r]; %#ok<AGROW>
        trace(out, P, r, fullfile(outdir, sprintf('%s_%s.png', configs{c}, suffixes{mo})));
    end
end

fprintf('\n%-12s %-20s %-6s %10s %10s %12s %10s %10s\n', 'config', 'loi', 'chute', 'max angle', 'tps 1 deg', 'max w roue', 'max i', 'i satur.');
fprintf('%-12s %-20s %-6s %10s %10s %12s %10s %10s\n', '', '', '', '(deg)', '(s)', '(tr/min)', '(A)', '(% tps)');
for r = R
    fprintf('%-12s %-20s %-6s %10.2f %10s %12.0f %10.1f %10.1f\n', r.config, r.loi, oui_non(r.chute), r.max_angle_deg, ...
        tps(r.t_1deg), r.max_w_rpm, r.max_i, r.pct_sat_i);
end
end

function r = indicateurs(out, P)
th = out.Theta; t = th.Time; ang = squeeze(th.Data);
if size(ang, 1) == 2 && size(ang, 2) ~= 2, ang = ang'; end
w = donnees(out.w); i = donnees(out.i);
r.t_fin = t(end);
r.chute = t(end) < P.scen.Tf - 1e-6 || max(abs(ang(:))) > P.scen.angle_chute;
r.max_angle_deg = rad2deg(max(abs(ang(:))));
% Temps après lequel |angle| reste sous 1 degré jusqu'à la première perturbation
avant = t < P.scen.pert(1);
hors = find(any(abs(ang(avant, :)) > deg2rad(1), 2), 1, 'last');
if r.chute, r.t_1deg = NaN; elseif isempty(hors), r.t_1deg = 0; else, r.t_1deg = t(min(hors + 1, numel(t))); end
r.max_w_rpm = max(abs(w(:))) * 60 / (2 * pi);
r.max_i = max(abs(i(:)));
actifs = any(P.B ~= 0, 1);
r.pct_sat_i = 100 * mean(any(abs(i(:, actifs)) >= 0.999 * P.mot.Imax, 2));
end

function d = donnees(ts)
d = squeeze(ts.Data);
if size(d, 1) ~= numel(ts.Time), d = d'; end
end

function trace(out, P, r, fichier)
f = figure('Visible', 'off', 'Position', [100 100 1100 780], 'Color', 'w');
try, f.Theme = 'light'; catch, end
tl = tiledlayout(f, 2, 2, 'TileSpacing', 'compact', 'Padding', 'compact');
title(tl, sprintf('%s · %s · %s%s', strrep(P.config, '_', ' '), P.mot.nom, r.loi, ternaire(r.chute, ' · CHUTE', '')), 'FontWeight', 'bold');

nexttile; th = out.Theta; plot(th.Time, rad2deg(donnees(th)), 'LineWidth', 1.3); grid on;
ylabel('angle (deg)'); title('Inclinaison du corps'); legend({'roulis \phi', 'tangage \theta'}, 'Location', 'best');
tp = P.scen.pert([1 4]); lab = {'poussée roulis', 'poussée tangage'}; garde = tp < th.Time(end) & P.scen.pert([3 6]) ~= 0;
if any(garde), xline(tp(garde), ':', lab(garde), 'HandleVisibility', 'off'); end
xlim([0 th.Time(end)]);

nexttile; w = out.w; actifs = find(any(P.B ~= 0, 1));
plot(w.Time, donnees(w) * 60 / (2 * pi), 'LineWidth', 1.1); grid on; hold on;
yline([-1 1] * P.mot.wmax * 60 / (2 * pi), 'r--', 'HandleVisibility', 'off');
ylabel('vitesse (tr/min)'); title('Vitesse des roues (- - : vitesse maximale)');
legend(arrayfun(@(k) sprintf('roue %d', k), 1:4, 'UniformOutput', false), 'Location', 'best');
if numel(actifs) < 4, subtitle(sprintf('roue(s) active(s) : %s', num2str(actifs))); end

nexttile; i = out.i; plot(i.Time, donnees(i), 'LineWidth', 1.1); grid on; hold on;
yline([-1 1] * P.mot.Imax, 'r--', 'HandleVisibility', 'off');
ylabel('courant (A)'); xlabel('temps (s)'); title('Courant des moteurs (- - : limite)');

nexttile; v = out.v; plot(v.Time, donnees(v), 'LineWidth', 1.3); grid on; hold on;
yline([-1 1] * max(P.v_max), 'r--', 'HandleVisibility', 'off');
ylabel('couple (N.m)'); xlabel('temps (s)'); title('Couple demandé par axe v = B\tau');
legend({'v_x (roulis)', 'v_y (tangage)'}, 'Location', 'best');

exportgraphics(f, fichier, 'Resolution', 110);
close(f);
end

function s = oui_non(b)
s = ternaire(b, 'OUI', 'non');
end

function s = tps(x)
if isnan(x), s = '-'; else, s = sprintf('%.2f', x); end
end

function y = ternaire(c, a, b)
if c, y = a; else, y = b; end
end

% Contrôle de la commande complète sur le banc équilibré : référence, manche, commande haut niveau, conversion, commande
% bas niveau, Perception. Les essais sont joués sur le jumeau Simscape, puis sur le jumeau Webots, avec les mêmes réglages.
% Avant de lancer avec Webots : ouvrir webots/worlds/banc_stabilisation.wbt (message « jumeau Webots prêt »).
% Le modèle n'est jamais enregistré : les réglages des essais sont perdus à la fermeture. Pendant les essais, le manche de
% l'interface de pilotage est remplacé par un scénario (pilotage_banc('scenario', ...)).
% Usage : verifier_commande_complete            (les deux jumeaux)
%         verifier_commande_complete Simscape   (un seul)
function verifier_commande_complete(varargin)
ici = fileparts(mfilename('fullpath'));
dossier = fileparts(ici);
nom = 'jumeau_banc_rw';
if nargin > 0, variantes = varargin; else, variantes = {'Simscape', 'Webots'}; end
if bdIsLoaded(nom), close_system(nom, 0); end
load_system(fullfile(dossier, [nom '.slx']));
set_param(nom, 'SimMechanicsOpenEditorOnUpdate', 'off', 'EnablePacing', 'off');
set_param([nom '/Pupitre/Mode : manuel (haut) ou commande (bas)'], 'sw', '0');   % la commande pilote les ESC
set_param([nom '/Pupitre/Marche (haut) ou arrêt (bas)'], 'sw', '1');
mws = get_param(nom, 'ModelWorkspace'); code0 = mws.MATLABCode;
fermer = onCleanup(@() fin(nom));
cao = jsondecode(fileread(fullfile(dossier, 'construction', 'cao_jumeau.json')));
% montage commun : banc équilibré, axes libres, tenu jusqu'à 2 s, départ à (2° ; -1°), pas de poussée, référence à plat
base = {'blocage_roulis', '0'; 'blocage_tangage', '0'; 'pivot_mm', '25'; 'angle0_roulis_deg', '2'; 'angle0_tangage_deg', '-1'; ...
    't_lacher', '2'; 'desat_active', '0'; 'perturbation_t', '7'; 'perturbation_duree', '0.2'; 'perturbation_couple', '[0 0]'; ...
    'ref_t', '[2 12]'; 'ref_roulis_deg', '[0 0]'; 'ref_tangage_deg', '[0 0]'};
sans_manche = zeros(1, 7);
manche = [0 1 0 0 0 0 0; 4 1 8 0 0 0 0; 8 1 8 -6 0 0 0; 12 1 0 0 0 0 0; 14 1 0 0 0.03 0 0.2; 15 1 0 0 0 0 0; 17 1 -10 10 0 0 0];
R = struct();

for v = 1:numel(variantes)
    var = variantes{v};
    set_param([nom '/Procédé'], 'LabelModeActiveChoice', var);
    fprintf('\n=================== jumeau %s\n', var);

    %% 1. Lâcher à 2 s, poussée de 0,02 N.m à 7 s sur les deux axes, roulis de 5° demandé à 12 s
    r = essai(nom, code0, [base; {'perturbation_couple', '[0.02 0.02]'; 'ref_roulis_deg', '[0 5]'}], 20, sans_manche);
    e = r.angles - r.ref;
    fprintf(['1. lâcher : écart à la référence %.2f° au plus (2 à 7 s) ; poussée : %.2f° au plus, %.2f° 2 s après ; ' ...
        'roulis de 5° : %.2f° à 20 s ; roues de %.0f à %.0f rad/s ; courant %.1f A au plus\n'], ...
        max(max(abs(e(r.t > 2 & r.t < 7, :)))), max(max(abs(e(r.t >= 7 & r.t < 9, :)))), max(max(abs(e(r.t > 9 & r.t < 9.3, :)))), ...
        r.angles(end, 1), min(min(r.roues(r.t > 2.5, :))), max(r.roues(:)), max(abs(r.courants(:))));
    R.(var).complet = r;

    %% 2. Tenue d'une inclinaison : 10° de roulis et -8° de tangage dès 5 s, poussée de 0,03 N.m à 15 s, jusqu'à 40 s
    r = essai(nom, code0, [base; {'ref_t', '[2 5]'; 'ref_roulis_deg', '[0 10]'; 'ref_tangage_deg', '[0 -8]'; ...
        'perturbation_t', '15'; 'perturbation_couple', '[0.03 0.03]'}], 40, sans_manche);
    e = r.angles - r.ref;
    k1 = r.t > 7 & r.t < 15; k2 = r.t > 18;
    dw = @(k) max(abs(r.roues(find(k, 1, 'last'), :) - r.roues(find(k, 1), :)));
    fprintf(['2. tenue de (10° ; -8°) : écart %.2f° au plus de 7 à 15 s, %.2f° de 18 à 40 s ; à 40 s : (%.2f° ; %.2f°) ; ' ...
        'dérive des roues %.1f rad/s de 7 à 15 s, %.1f rad/s de 18 à 40 s ; réserve à 40 s : %.0f %%\n'], ...
        max(max(abs(e(k1, :)))), max(max(abs(e(k2, :)))), r.angles(end, 1), r.angles(end, 2), dw(k1), dw(k2), 100 * r.reserve(end));
    R.(var).tenue = r;
    % Perception, sur cet essai (après le lâcher)
    k = r.te > 2.5;
    qv = interp1(r.t, r.angles, r.te(k)); dqv = interp1(r.t, r.vitesses, r.te(k)) * pi/180; wv = interp1(r.t, r.roues, r.te(k));
    Hv = interp1(r.t, r.H_vrai, r.te(k));
    ea = r.ang_p(k, :) - qv; vu = all(r.vues(k, :) > 0.5, 2);
    fprintf(['   Perception : angles à %.3f° près (écart type), %.2f° au plus ; vitesses des axes à %.3f rad/s près ; ' ...
        'vitesses des roues à %.1f rad/s au plus, signe juste %.1f %% du temps ; moment cinétique à %.1e N.m.s au plus ; ' ...
        'déséquilibre estimé (%.3f ; %.3f) mm\n'], std(ea(:)), max(abs(ea(:))), std(reshape(r.vit_p(k, :) - dqv, [], 1)), ...
        max(max(abs(r.roues_p(k, :) - wv) .* vu)), 100 * mean(sign(r.roues_p(k, :)) == sign(wv), 'all'), ...
        max(max(abs(r.H_p(k, :) - Hv))), mean(r.deseq(r.te > 30, 1)), mean(r.deseq(r.te > 30, 2)));
    R.(var).perception = struct('t', r.te(k), 'erreur', ea);

    %% 3. Poussée forte : 0,05 N.m pendant 0,2 s sur le roulis
    r = essai(nom, code0, [base; {'perturbation_couple', '[0.05 0]'}], 14, sans_manche);
    e = r.angles - r.ref;
    k = r.t >= 7; tr = r.t(find(k & abs(e(:, 1)) > 0.5, 1, 'last'));
    if isempty(tr), tr = 7; end
    fprintf('3. poussée de 0,05 N.m sur le roulis : écart %.2f° au plus ; revenu à moins de 0,5° %.1f s après ; butées %s\n', ...
        max(abs(e(k, 1))), tr - 7, oui_non(max(abs(r.angles(:))) > 19.5));
    R.(var).poussee = r;

    %% 4. Manche : roulis 8° à 4 s, tangage -6° à 8 s, à plat à 12 s, poussée du manche à 14 s, (-10° ; 10°) à 17 s
    r = essai(nom, code0, base, 22, manche);
    a = @(t) interp1(r.t, r.angles, t);
    hors = r.t > 2.5 & (r.t < 14 | r.t > 16);
    fprintf(['4. manche : (%.2f° ; %.2f°) à 7,5 s pour (8 ; 0) ; (%.2f° ; %.2f°) à 11,5 s pour (8 ; -6) ; (%.2f° ; %.2f°) à 13,5 s ' ...
        'pour (0 ; 0) ; (%.2f° ; %.2f°) à 22 s pour (-10 ; 10) ; écart à la référence %.2f° au plus hors poussée\n'], ...
        a(7.5), a(11.5), a(13.5), r.angles(end, :), max(max(abs(r.angles(hors, :) - r.ref(hors, :)))));
    R.(var).manche = r;

    %% 5. Banc déséquilibré de 1 mm (paliers non remontés, rangée +24) : tenue de (10° ; -8°)
    r = essai(nom, code0, [base; {'pivot_mm', '24'; 'ref_t', '[2 5]'; 'ref_roulis_deg', '[0 10]'; 'ref_tangage_deg', '[0 -8]'}], 30, sans_manche);
    h = cao.controle.G_disp(3) * 1000 - 24; md = cao.controle.m_disp; mc = cao.controle.m_croix; hc = cao.controle.G_croix(3) * 1000 - 24;   % hauteur du centre de masse du croisillon au-dessus du pivot
    q = interp1(r.t, r.angles, r.te) * pi/180;
    vrai = [h * sin(q(:, 2)), -(md * h * cos(q(:, 2)) + mc * hc) .* sin(q(:, 1)) / (md + mc)];
    k = r.te > 9 & r.te < 15;
    ts = r.te(find(r.reserve < 0.01 & r.te > 5, 1));
    if isempty(ts), ts = NaN; end
    fprintf(['5. déséquilibre de %.2f mm (rangée +24) : centre de masse estimé (%.3f ; %.3f) mm, réel (%.3f ; %.3f) mm de 9 à 15 s ; ' ...
        'roues à bout de réserve à %.1f s\n'], h, mean(r.deseq(k, 1)), mean(r.deseq(k, 2)), mean(vrai(k, 1)), mean(vrai(k, 2)), ts);
    r.deseq_vrai = vrai;
    R.(var).desequilibre = r;

    %% 6. Pivot bas (+8), banc déséquilibré de 17 mm : désaturation en marche
    r = essai(nom, code0, [base; {'pivot_mm', '8'; 'desat_active', '1'; 'perturbation_couple', '[0.02 0.02]'}], 20, sans_manche);
    fprintf('6. pivot +8 avec désaturation : (%.2f° ; %.2f°) à 20 s ; angles de %.1f° à %.1f° ; roues de %.0f à %.0f rad/s ; butées %s\n', ...
        r.angles(end, 1), r.angles(end, 2), min(r.angles(:)), max(r.angles(:)), min(min(r.roues(r.t > 2.5, :))), max(r.roues(:)), ...
        oui_non(max(abs(r.angles(:))) > 19.5));
    R.(var).pivot8 = r;
end
mws.MATLABCode = code0;

%% Comparaison des deux jumeaux
if all(isfield(R, {'Simscape', 'Webots'}))
    fprintf('\n=================== écart entre les deux jumeaux (Webots moins Simscape)\n');
    n = {'complet', 'lâcher, poussée, consigne'; 'tenue', 'tenue de (10° ; -8°)'; 'manche', 'manche'};
    for k = 1:size(n, 1)
        a = R.Simscape.(n{k, 1}); b = R.Webots.(n{k, 1});
        fprintf('%-26s : angles %.2f° au plus, vitesse des roues %.1f rad/s au plus\n', n{k, 2}, ...
            max(max(abs(b.angles - interp1(a.t, a.angles, b.t)))), max(max(abs(b.roues - interp1(a.t, a.roues, b.t)))));
    end
end
tracer(R, fullfile(ici, 'commande_complete.png'));
end

%% ------------------------------------------------------------------ outils
function fin(nom)
pilotage_banc('scenario', []);
if bdIsLoaded(nom), close_system(nom, 0); end
end

function s = oui_non(x)
if x, s = 'touchées'; else, s = 'non touchées'; end
end

function r = essai(nom, code0, paires, duree, scenario)
% Remet les réglages d'origine, applique ceux de l'essai (le dernier réglage d'un même nom l'emporte), simule.
mws = get_param(nom, 'ModelWorkspace');
code = code0;
for k = 1:size(paires, 1)
    code = regexprep(code, ['(?m)^' paires{k, 1} ' = [^;]*;'], [paires{k, 1} ' = ' paires{k, 2} ';']);
    assert(~isempty(regexp(code, ['(?m)^' paires{k, 1} ' = ' regexptranslate('escape', paires{k, 2}) ';'], 'once')), paires{k, 1});
end
mws.MATLABCode = code; mws.reload;
pilotage_banc('raz');
pilotage_banc('scenario', scenario);
out = sim(nom, 'StopTime', num2str(duree));
L = out.logsout;
g = L.get('grandeurs_reelles').Values;
r.t = g.angles_cardan.Time;
r.angles = col(g.angles_cardan); r.vitesses = col(g.vitesses_cardan); r.roues = col(g.roues_tr_min) * 2 * pi / 60; r.courants = col(g.courants_A);
J = mws.getVariable('J_roue');
r.H_vrai = J * cosd(45) * [r.roues * [1 -1 -1 1]', r.roues * [1 1 -1 -1]'];
tc = L.get('theta_ref').Values.Time;
r.ref = interp1(tc, col(L.get('theta_ref').Values) * 180 / pi, r.t, 'previous', 'extrap');   % référence vue par la commande
E = L.get('etat').Values;
r.te = E.angles_deg.Time;
r.ang_p = col(E.angles_deg); r.vit_p = col(E.vitesses); r.roues_p = col(E.vitesses_roues); r.vues = col(E.roues_vues);
r.H_p = col(E.moment_roues); r.deseq = col(E.desequilibre_mm); r.reserve = col(E.reserve_roues);
r.duree = out.SimulationMetadata.TimingInfo.ExecutionElapsedWallTime;
end

function x = col(ts)
x = squeeze(ts.Data);
if size(x, 1) ~= numel(ts.Time), x = x.'; end
end

function tracer(R, fichier)
var = fieldnames(R); var = var{1};
f = figure('Visible', 'off', 'Position', [0 0 1500 950]);
try, theme(f, 'light'); catch, end
bleu = [0.12 0.40 0.75]; rouge = [0.85 0.25 0.15]; gris = [0.45 0.45 0.45];
tiledlayout(f, 2, 3, 'TileSpacing', 'compact', 'Padding', 'compact');
web = isfield(R, 'Webots') && ~strcmp(var, 'Webots');
% 1. tenue d'une inclinaison
a = R.(var).tenue;
nexttile; hold on; grid on
plot(a.t, a.ref(:, 1), '--', 'Color', bleu); plot(a.t, a.ref(:, 2), '--', 'Color', rouge);
plot(a.t, a.angles(:, 1), 'Color', bleu, 'LineWidth', 1.4); plot(a.t, a.angles(:, 2), 'Color', rouge, 'LineWidth', 1.4);
noms = {'référence de roulis', 'référence de tangage', ['roulis (' var ')'], ['tangage (' var ')']};
if web, b = R.Webots.tenue; plot(b.t, b.angles, '-.', 'Color', gris); noms = [noms {'Webots'}]; end
xlabel('temps (s)'); ylabel('angle (°)'); title('Banc équilibré : (10° ; -8°) tenus, poussée à 15 s'); legend(noms, 'Location', 'best');
nexttile; hold on; grid on
plot(a.t, a.roues, 'LineWidth', 1.2); yline([60 400], 'k:');
xlabel('temps (s)'); ylabel('vitesse des roues (rad/s)'); title('Même essai : les roues ne dérivent pas');
% 2. manche
a = R.(var).manche;
nexttile; hold on; grid on
plot(a.t, a.ref(:, 1), '--', 'Color', bleu); plot(a.t, a.ref(:, 2), '--', 'Color', rouge);
plot(a.t, a.angles(:, 1), 'Color', bleu, 'LineWidth', 1.4); plot(a.t, a.angles(:, 2), 'Color', rouge, 'LineWidth', 1.4);
xlabel('temps (s)'); ylabel('angle (°)'); title('Manche : 8°, -6°, à plat, poussée, (-10° ; 10°)');
legend('référence de roulis', 'référence de tangage', 'roulis', 'tangage', 'Location', 'best');
% 3. poussée forte
a = R.(var).poussee;
nexttile; hold on; grid on
plot(a.t, a.ref(:, 1), '--', 'Color', bleu); plot(a.t, a.angles(:, 1), 'Color', bleu, 'LineWidth', 1.4); plot(a.t, a.angles(:, 2), 'Color', rouge, 'LineWidth', 1.4);
if web, b = R.Webots.poussee; plot(b.t, b.angles(:, 1), '-.', 'Color', gris); end
xlim([5 14]); xlabel('temps (s)'); ylabel('angle (°)'); title('Poussée de 0,05 N.m pendant 0,2 s sur le roulis');
legend('référence de roulis', 'roulis', 'tangage', 'Location', 'best');
% 4. Perception
p = R.(var).perception;
nexttile; hold on; grid on
plot(p.t, p.erreur(:, 1), 'Color', bleu); plot(p.t, p.erreur(:, 2), 'Color', rouge);
xlabel('temps (s)'); ylabel('angle perçu moins angle réel (°)'); title('Perception : angles tirés du quaternion');
legend('roulis', 'tangage', 'Location', 'best');
% 5. déséquilibre
a = R.(var).desequilibre;
nexttile; hold on; grid on
plot(a.te, a.deseq(:, 1), 'Color', bleu, 'LineWidth', 1.3); plot(a.te, a.deseq(:, 2), 'Color', rouge, 'LineWidth', 1.3);
plot(a.te, a.deseq_vrai(:, 1), ':', 'Color', bleu, 'LineWidth', 1.5); plot(a.te, a.deseq_vrai(:, 2), ':', 'Color', rouge, 'LineWidth', 1.5);
ylim([-0.3 0.1]); ylabel('centre de masse par rapport au pivot (mm)');
yyaxis right; plot(a.te, 100 * a.reserve, 'Color', gris); ylabel('réserve des roues (%)'); ylim([0 105]);
xlabel('temps (s)'); title('Déséquilibre de 1 mm : estimé (traits pleins) et réel (pointillés)');
legend('estimé, selon X', 'estimé, selon Y', 'réel, selon X', 'réel, selon Y', 'réserve', 'Location', 'southwest');
exportgraphics(f, fichier, 'Resolution', 120);
close(f);
fprintf('figure : %s\n', fichier);
end

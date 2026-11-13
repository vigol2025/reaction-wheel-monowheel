% Contrôle de la commande bas niveau (boucle de vitesse de chaque roue, avec observateur CFO).
% Les essais sont joués sur le jumeau Simscape, puis sur le jumeau Webots, avec les mêmes réglages.
% Avant de lancer avec Webots : ouvrir webots/worlds/banc_stabilisation.wbt (message « jumeau Webots prêt »).
% Le modèle n'est jamais enregistré : les réglages des essais sont perdus à la fermeture.
% Usage : verifier_commande_bas_niveau            (les deux jumeaux)
%         verifier_commande_bas_niveau Simscape   (un seul)
function verifier_commande_bas_niveau(varargin)
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
pilotage_banc('scenario', zeros(1, 7));   % pendant les essais, le manche de l'interface de pilotage ne joue pas
fermer = onCleanup(@() fin(nom));
bloque = {'blocage_roulis', '1'; 'blocage_tangage', '1'};
R = struct();

for v = 1:numel(variantes)
    var = variantes{v};
    set_param([nom '/Procédé'], 'LabelModeActiveChoice', var);
    fprintf('\n=================== jumeau %s\n', var);

    %% 1. Une roue : 0, puis 150 rad/s, puis 0 (axes bloqués)
    r = essai(nom, code0, [bloque; {'essai_roue_vitesse1', '[150 0 0 0]'; 'essai_roue_vitesse2', '[0 0 0 0]'}], 10);
    e = r.w(:, 1) - r.wr(:, 1);
    fprintf(['1. roue 1 seule : erreur de suivi %.1f rad/s au plus pendant les rampes, %.2f rad/s sur le palier (4 à 6 s), %.1f rad/s à l''arrêt (9 à 10 s)\n' ...
        '   estimation du CFO : %.1f rad/s d''écart au plus ; impulsions de %d à %d µs ; courant %.1f A au plus ; autres roues : %.2g rad/s au plus\n'], ...
        max(abs(e)), max(abs(e(r.tc > 4 & r.tc < 6))), max(abs(e(r.tc > 9))), max(abs(r.we(:, 1) - r.w(:, 1))), ...
        min(r.imp(:, 1)), max(r.imp(:, 1)), max(abs(r.courants(:, 1))), max(max(abs(r.roues(:, 2:4)))));
    R.(var).une = r;

    %% 2. Inversion du sens : +150 puis -150 rad/s
    r = essai(nom, code0, [bloque; {'essai_roue_vitesse1', '[150 0 0 0]'; 'essai_roue_vitesse2', '[-150 0 0 0]'}], 10);
    e = r.w(:, 1) - r.wr(:, 1);
    k = r.tc > 6 & r.tc < 7.2;
    fprintf('2. inversion +150 vers -150 rad/s : erreur %.1f rad/s au plus pendant l''inversion, %.2f rad/s sur le palier final ; courant %.1f A au plus\n', ...
        max(abs(e(k))), max(abs(e(r.tc > 9))), max(abs(r.courants(r.t > 6, 1))));
    R.(var).inversion = r;

    %% 3. Modèle faux : moteur réel à 0,12 ohm et ESC avec 10 µs de zone morte, commande réglée sur 0,08 ohm et 0 µs
    m = get_param(nom, 'ModelWorkspace');
    a0 = m.getVariable('a0_roue'); a1 = m.getVariable('a1_roue'); wc = m.getVariable('wc_roue');
    Kt = m.getVariable('Kt'); Ke = m.getVariable('Ke'); J = m.getVariable('J_roue'); f = m.getVariable('f_roue');
    Va = m.getVariable('V_alim'); imax = m.getVariable('imp_max'); ineutre = m.getVariable('imp_neutre');
    Rr = 0.12; zm = 10;
    r = essai(nom, code0, [bloque; {'essai_roue_vitesse1', '[150 0 0 0]'; 'essai_roue_vitesse2', '[150 0 0 0]'; 'R_moteur', num2str(Rr); ...
        'zone_morte_us', num2str(zm); 'a0_roue', sprintf('%.10g * [1 1 1 1]', a0(1)); 'a1_roue', sprintf('%.10g * [1 1 1 1]', a1(1))}], 8);
    a0r = Kt / (Rr * J); a1r = (Kt * Ke / Rr + f) / J; Vzm = zm * Va / (imax - ineutre);
    V = a1r * 150 / a0r + Vzm;                                  % tension qu'il faut au moteur réel pour tenir 150 rad/s
    d = (a1(1) - a1r) * 150 + (a0r - a0(1)) * V - a0r * Vzm;    % ce que le modèle de la commande ne voit pas
    e = r.w(:, 1) - r.wr(:, 1);
    k = r.tc > 6;
    fprintf(['3. modèle faux : perturbation estimée %.0f rad/s² en fin (calcul %.0f) ; erreur de suivi %.2f rad/s sur le palier (6 à 8 s)\n' ...
        '   sans compensation, l''erreur resterait à d / wc = %.0f rad/s\n'], mean(r.de(k, 1)), d, max(abs(e(k))), d / wc(1));
    R.(var).faux = r; R.(var).d_calcul = d;

    %% 4. Quatre roues ensemble (axes bloqués)
    r = essai(nom, code0, [bloque; {'essai_roue_vitesse1', '[150 -120 90 -60]'; 'essai_roue_vitesse2', '[-60 90 -120 150]'}], 10);
    e = r.w - r.wr;
    fprintf('4. quatre roues : erreur au plus %s rad/s pendant les rampes ; %s rad/s sur les paliers (4 à 6 s et 9 à 10 s)\n', ...
        mat2str(max(abs(e)), 3), mat2str(max(abs(e((r.tc > 4 & r.tc < 6) | r.tc > 9, :))), 2));
    R.(var).quatre = r;

    %% 5. Quatre roues, les deux axes libres : le dispositif bouge et tombe sur ses butées pendant que les roues suivent leur consigne
    r = essai(nom, code0, {'essai_roue_vitesse1', '[150 -120 90 -60]'; 'essai_roue_vitesse2', '[-60 90 -120 150]'}, 10);
    e = r.w - r.wr;
    fprintf('5. axes libres : erreur au plus %s rad/s pendant les rampes ; %s rad/s sur les paliers ; cardan de %.1f° à %.1f°\n', ...
        mat2str(max(abs(e)), 3), mat2str(max(abs(e((r.tc > 4 & r.tc < 6) | r.tc > 9, :))), 2), min(r.angles(:)), max(r.angles(:)));
    R.(var).libre = r;

    %% 6. Consigne hors d'atteinte : 500 rad/s demandés, les impulsions sont bornées, puis retour à 150 rad/s
    r = essai(nom, code0, [bloque; {'essai_roue_vitesse1', '[500 0 0 0]'; 'essai_roue_vitesse2', '[150 0 0 0]'}], 10);
    e = r.w(:, 1) - r.wr(:, 1);
    fprintf('6. saturation : impulsion bornée à %d µs, roue à %.0f rad/s (demandé : 500) ; retour à 150 rad/s : erreur %.2f rad/s de 9 à 10 s\n', ...
        max(r.imp(:, 1)), max(r.w(:, 1)), max(abs(e(r.tc > 9))));
    R.(var).saturation = r;
end
mws.MATLABCode = code0;

%% Comparaison des deux jumeaux
if all(isfield(R, {'Simscape', 'Webots'}))
    fprintf('\n=================== écart entre les deux jumeaux (Webots moins Simscape)\n');
    n = {'une', 'une roue'; 'inversion', 'inversion'; 'quatre', 'quatre roues'};
    for k = 1:size(n, 1)
        a = R.Simscape.(n{k, 1}); b = R.Webots.(n{k, 1});
        fprintf('%-14s : vitesse des roues %.1f rad/s au plus\n', n{k, 2}, max(max(abs(b.roues - interp1(a.t, a.roues, b.t)))));
    end
end
tracer(R, fullfile(ici, 'commande_bas_niveau.png'));
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
% commande bas niveau seule : pas de maintien, pas de poussée, commande haut niveau à l'arrêt, roues sans vitesse de repos
paires = [paires; {'t_lacher', '0'; 'perturbation_couple', '[0 0]'; 't_depart', '1e9'; 'w_repos', '0'; 'w_roue_min', '-400'}];
for k = 1:size(paires, 1)
    code = regexprep(code, ['(?m)^' paires{k, 1} ' = [^;]*;'], [paires{k, 1} ' = ' paires{k, 2} ';']);
    assert(~isempty(regexp(code, ['(?m)^' paires{k, 1} ' = ' regexptranslate('escape', paires{k, 2}) ';'], 'once')), paires{k, 1});
end
mws.MATLABCode = code; mws.reload;
out = sim(nom, 'StopTime', num2str(duree));
L = out.logsout;
g = L.get('grandeurs_reelles').Values;
r.t = g.roues_tr_min.Time;
r.roues = col(g.roues_tr_min) * 2 * pi / 60; r.courants = col(g.courants_A); r.angles = col(g.angles_cardan);
r.tc = L.get('omega_ref').Values.Time;                      % instants de calcul de la commande
r.wr = col(L.get('omega_ref').Values); r.wm = col(L.get('omega_mes').Values); r.we = col(L.get('omega_est').Values);
r.de = col(L.get('d_est').Values); r.V = col(L.get('V_appliquee').Values); r.voit = col(L.get('capteur_voit').Values);
r.imp = interp1(L.get('imp').Values.Time, col(L.get('imp').Values), r.tc, 'previous', 'extrap');
r.w = interp1(r.t, r.roues, r.tc);                          % vitesse réelle des roues aux instants de la commande
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
bleu = [0.12 0.40 0.75]; rouge = [0.85 0.25 0.15]; vert = [0.2 0.6 0.2]; gris = [0.45 0.45 0.45];
tiledlayout(f, 2, 3, 'TileSpacing', 'compact', 'Padding', 'compact');
titres = {'une', 'Roue 1 seule : 0, 150 rad/s, puis 0'; 'inversion', 'Roue 1 : inversion de +150 à -150 rad/s'};
for k = 1:2
    nexttile; hold on; grid on
    a = R.(var).(titres{k, 1});
    plot(a.tc, a.wr(:, 1), 'k--', 'LineWidth', 1.3); plot(a.t, a.roues(:, 1), 'Color', bleu, 'LineWidth', 1.4);
    stairs(a.tc, a.wm(:, 1), 'Color', vert); stairs(a.tc, a.we(:, 1), ':', 'Color', rouge, 'LineWidth', 1.4);
    noms = {'référence', ['vitesse réelle (' var ')'], 'mesure avec signe', 'estimation du CFO'};
    if isfield(R, 'Webots') && ~strcmp(var, 'Webots')
        b = R.Webots.(titres{k, 1}); plot(b.t, b.roues(:, 1), '-.', 'Color', gris, 'LineWidth', 1.2); noms{end + 1} = 'vitesse réelle (Webots)'; %#ok<AGROW>
    end
    xlabel('temps (s)'); ylabel('vitesse de la roue 1 (rad/s)'); title(titres{k, 2}); legend(noms, 'Location', 'best');
end
nexttile; hold on; grid on
a = R.(var).faux;
stairs(a.tc, a.de(:, 1), 'Color', bleu, 'LineWidth', 1.3); yline(R.(var).d_calcul, 'k--', 'LineWidth', 1.2);
xlabel('temps (s)'); ylabel('perturbation estimée (rad/s²)'); title('Modèle faux (0,12 ohm, zone morte 10 µs) : estimation du CFO');
legend('d estimée', 'calcul', 'Location', 'best');
nexttile; hold on; grid on
a = R.(var).quatre; c = lines(4);
for j = 1:4
    plot(a.tc, a.wr(:, j), '--', 'Color', c(j, :)); plot(a.t, a.roues(:, j), 'Color', c(j, :), 'LineWidth', 1.3);
end
xlabel('temps (s)'); ylabel('vitesse des roues (rad/s)'); title('Quatre roues ensemble : références (tirets) et vitesses réelles');
nexttile; hold on; grid on
a = R.(var).une;
stairs(a.tc, a.imp(:, 1), 'Color', bleu, 'LineWidth', 1.2); ylabel('impulsion de l''ESC 1 (µs)');
yyaxis right; plot(a.t, a.courants(:, 1), 'Color', rouge); ylabel('courant du moteur 1 (A)');
xlabel('temps (s)'); title('Roue 1 seule : impulsion et courant');
nexttile; hold on; grid on
a = R.(var).saturation;
plot(a.tc, a.wr(:, 1), 'k--', 'LineWidth', 1.3); plot(a.t, a.roues(:, 1), 'Color', bleu, 'LineWidth', 1.4);
ylabel('vitesse de la roue 1 (rad/s)'); yyaxis right; stairs(a.tc, a.imp(:, 1), 'Color', rouge); ylabel('impulsion (µs)');
xlabel('temps (s)'); title('Consigne hors d''atteinte (500 rad/s), puis 150 rad/s'); legend('référence', 'vitesse réelle', 'impulsion', 'Location', 'best');
exportgraphics(f, fichier, 'Resolution', 120);
close(f);
fprintf('figure : %s\n', fichier);
end

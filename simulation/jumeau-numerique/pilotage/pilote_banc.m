function app = pilote_banc()
% PILOTE_BANC  Interface de pilotage du banc de stabilisation, à la manière d'une manette de drone.
%
%   pilote_banc            ouvre l'interface (et charge le modèle jumeau_banc_rw s'il ne l'est pas)
%
% Manche (à gauche) : il donne l'inclinaison demandée. Vu de dessus, le banc penche du côté où l'on pousse le manche.
% Lâché, le manche revient au centre (banc à plat), sauf si « Garder l'inclinaison » est coché. Les flèches du clavier
% font la même chose. Poussées (au centre) : un appui bref sur un côté du banc, comme avec le doigt.
% Simulation (au centre) : choix du jumeau, démarrage, arrêt, moteurs. État du banc (à droite) : angles mesurés par la
% Perception, vitesses des roues, réserve des roues, déséquilibre du banc.
%
% L'interface et le modèle s'échangent leurs données par pilotage_banc.m. La simulation peut aussi être lancée depuis
% Simulink (bouton Run) : tant que l'interface est ouverte, le manche pilote la référence.

dossier = fileparts(fileparts(mfilename('fullpath')));
mdl = 'jumeau_banc_rw';
if ~bdIsLoaded(mdl)
    load_system(fullfile(dossier, [mdl '.slx']));
end
addpath(fullfile(dossier, 'pilotage'));

% ------------------------------------------------------------------ état de l'interface
A = 10;                 % inclinaison demandée manche à fond (°)
manche = [0 0];         % position du manche, dans le disque unité (x vers +X, y vers +Y, vu de dessus)
glisse = false;         % le manche est tenu à la souris
fleches = struct('haut', 0, 'bas', 0, 'gauche', 0, 'droite', 0);
lance_ici = false;      % la simulation a été lancée par l'interface
stop_origine = '';
rythme_origine = '';    % rythme de Simulink (Simulation Pacing) avant le lancement
recu = false;           % des données sont arrivées pendant la simulation en cours
t_lance = tic;          % instant du dernier démarrage demandé
vu_en_cours = false;    % la simulation lancée a été vue en cours
n_recus = 0;            % envois du tableau de bord reçus
virgule = @(x, f) strrep(sprintf(f, x), '.', ',');

% ------------------------------------------------------------------ fenêtre
fig = uifigure('Name', 'Pilotage du banc de stabilisation', 'Position', [80 60 1080 660], 'Resize', 'off');
fig.CloseRequestFcn = @fermer;
uilabel(fig, 'Text', 'Pilotage du banc de stabilisation', 'Position', [20 615 600 34], 'FontSize', 20, 'FontWeight', 'bold');
message = uilabel(fig, 'Text', 'Choisis le jumeau, puis Démarrer. Webots : ouvre d''abord le monde banc_stabilisation.wbt.', ...
    'Position', [20 12 1040 40], 'WordWrap', 'on', 'FontSize', 13);

% --- manche
pm = uipanel(fig, 'Title', 'Manche : inclinaison demandée', 'Position', [20 62 370 545], 'FontSize', 13, 'FontWeight', 'bold');
pad = uiaxes(pm, 'Position', [15 175 340 340]);
pad.XLim = [-1.25 1.25]; pad.YLim = [-1.25 1.25];
pad.DataAspectRatio = [1 1 1];
pad.XTick = []; pad.YTick = []; pad.Box = 'on';
pad.Toolbar.Visible = 'off';
disableDefaultInteractivity(pad);
hold(pad, 'on');
a = linspace(0, 2*pi, 181);
plot(pad, cos(a), sin(a), 'Color', [0.55 0.55 0.55], 'LineWidth', 1.5, 'HitTest', 'off');
plot(pad, 0.5 * cos(a), 0.5 * sin(a), ':', 'Color', [0.7 0.7 0.7], 'HitTest', 'off');
plot(pad, [-1 1], [0 0], 'Color', [0.8 0.8 0.8], 'HitTest', 'off');
plot(pad, [0 0], [-1 1], 'Color', [0.8 0.8 0.8], 'HitTest', 'off');
o = linspace(pi/8, 2*pi + pi/8, 9);                % le banc vu de dessus : corps octogonal
plot(pad, 0.22 * cos(o), 0.22 * sin(o), 'Color', [0.35 0.45 0.6], 'LineWidth', 1.2, 'HitTest', 'off');
text(pad, 1.13, 0, '+X', 'HorizontalAlignment', 'center', 'FontWeight', 'bold', 'HitTest', 'off');
text(pad, -1.13, 0, '-X', 'HorizontalAlignment', 'center', 'FontWeight', 'bold', 'HitTest', 'off');
text(pad, 0, 1.13, '+Y', 'HorizontalAlignment', 'center', 'FontWeight', 'bold', 'HitTest', 'off');
text(pad, 0, -1.13, '-Y', 'HorizontalAlignment', 'center', 'FontWeight', 'bold', 'HitTest', 'off');
mesure = plot(pad, 0, 0, 'o', 'MarkerSize', 16, 'MarkerFaceColor', [0.85 0.3 0.2], 'MarkerEdgeColor', 'none', 'HitTest', 'off');
bouton = plot(pad, 0, 0, 'o', 'MarkerSize', 34, 'MarkerFaceColor', 'none', 'MarkerEdgeColor', [0.05 0.4 0.5], 'LineWidth', 3, 'HitTest', 'off');
lab_manche = uilabel(pm, 'Text', '', 'Position', [15 145 340 24], 'FontSize', 13, 'HorizontalAlignment', 'center');
uilabel(pm, 'Text', ['Vu de dessus : le banc penche du côté où l'on pousse le manche. Cercle bleu : le manche. ' ...
    'Point rouge : le banc mesuré. Clavier : flèches.'], 'Position', [15 100 340 44], 'WordWrap', 'on', 'FontSize', 11);
uilabel(pm, 'Text', 'Inclinaison à fond', 'Position', [15 70 110 22]);
curseur = uislider(pm, 'Limits', [2 15], 'Value', A, 'Position', [135 82 160 3], 'MajorTicks', [2 5 10 15], ...
    'ValueChangedFcn', @(~, ev) amplitude(ev.Value));
lab_amp = uilabel(pm, 'Text', '10°', 'Position', [305 70 50 22]);
garder = uicheckbox(pm, 'Text', 'Garder l''inclinaison quand on lâche le manche', 'Position', [15 33 340 22], 'Value', false);
uibutton(pm, 'Text', 'Remettre à plat', 'Position', [15 5 140 26], 'ButtonPushedFcn', @(~, ~) regler([0 0]));
suivre = uicheckbox(pm, 'Text', 'Le manche pilote', 'Position', [200 5 160 26], 'Value', true, ...
    'ValueChangedFcn', @(~, ev) pilotage_banc('actif', ev.Value), 'Tooltip', 'Décoché : la référence programmée du modèle s''applique');

% --- poussées
pp = uipanel(fig, 'Title', 'Poussées : appuyer sur un côté', 'Position', [405 330 320 277], 'FontSize', 13, 'FontWeight', 'bold');
uibutton(pp, 'Text', 'Côté +Y', 'Position', [110 175 100 36], 'ButtonPushedFcn', @(~, ~) pousser('+Y'));
uibutton(pp, 'Text', 'Côté -Y', 'Position', [110 75 100 36], 'ButtonPushedFcn', @(~, ~) pousser('-Y'));
uibutton(pp, 'Text', 'Côté -X', 'Position', [10 125 100 36], 'ButtonPushedFcn', @(~, ~) pousser('-X'));
uibutton(pp, 'Text', 'Côté +X', 'Position', [210 125 100 36], 'ButtonPushedFcn', @(~, ~) pousser('+X'));
uilabel(pp, 'Text', 'banc', 'Position', [140 130 40 24], 'HorizontalAlignment', 'center', 'FontColor', [0.35 0.45 0.6]);
uilabel(pp, 'Text', 'Couple (N.m)', 'Position', [10 38 90 22]);
force = uispinner(pp, 'Limits', [0.005 0.08], 'Step', 0.005, 'Value', 0.03, 'ValueDisplayFormat', '%.3f', 'Position', [100 38 80 22]);
uilabel(pp, 'Text', 'pendant 0,2 s', 'Position', [190 38 120 22]);
lab_poussee = uilabel(pp, 'Text', '', 'Position', [10 8 300 24], 'FontColor', [0.4 0.4 0.4]);

% --- simulation
ps = uipanel(fig, 'Title', 'Simulation', 'Position', [405 62 320 255], 'FontSize', 13, 'FontWeight', 'bold');
uilabel(ps, 'Text', 'Jumeau', 'Position', [12 195 60 22]);
jumeau = uidropdown(ps, 'Items', {'Simscape', 'Webots'}, 'Value', get_param([mdl '/Procédé'], 'LabelModeActiveChoice'), 'Position', [80 195 120 22]);
b_demarrer = uibutton(ps, 'Text', 'Démarrer', 'Position', [12 145 140 36], 'FontWeight', 'bold', 'ButtonPushedFcn', @demarrer);
b_arreter = uibutton(ps, 'Text', 'Arrêter', 'Position', [165 145 140 36], 'Enable', 'off', 'ButtonPushedFcn', @arreter);
moteurs = uicheckbox(ps, 'Text', 'Moteurs en marche', 'Position', [12 108 200 24], 'Value', true, 'ValueChangedFcn', @marche);
uilabel(ps, 'Text', 'Durée (s)', 'Position', [12 75 70 22]);
duree = uispinner(ps, 'Limits', [10 3600], 'Step', 10, 'Value', 300, 'Position', [80 75 80 22]);
lampe = uilamp(ps, 'Position', [12 40 20 20], 'Color', [0.6 0.6 0.6]);
lab_statut = uilabel(ps, 'Text', 'Arrêtée', 'Position', [40 38 270 24], 'FontSize', 13);
lab_t = uilabel(ps, 'Text', '', 'Position', [12 8 290 24], 'FontColor', [0.4 0.4 0.4]);

% --- état du banc
pe = uipanel(fig, 'Title', 'État du banc (Perception)', 'Position', [740 62 320 545], 'FontSize', 13, 'FontWeight', 'bold');
uilabel(pe, 'Text', 'Roulis', 'Position', [12 480 80 26], 'FontSize', 14);
lab_roulis = uilabel(pe, 'Text', '-', 'Position', [95 476 110 34], 'FontSize', 24, 'FontWeight', 'bold');
lab_roulis_ref = uilabel(pe, 'Text', '', 'Position', [205 480 110 26], 'FontColor', [0.4 0.4 0.4]);
uilabel(pe, 'Text', 'Tangage', 'Position', [12 440 80 26], 'FontSize', 14);
lab_tangage = uilabel(pe, 'Text', '-', 'Position', [95 436 110 34], 'FontSize', 24, 'FontWeight', 'bold');
lab_tangage_ref = uilabel(pe, 'Text', '', 'Position', [205 440 110 26], 'FontColor', [0.4 0.4 0.4]);
uilabel(pe, 'Text', 'Réserve des roues (%)', 'Position', [12 405 290 22], 'FontWeight', 'bold');
reserve = uigauge(pe, 'semicircular', 'Position', [60 300 200 105], 'Limits', [0 100], ...
    'ScaleColors', {[0.85 0.3 0.2], [0.95 0.75 0.2], [0.3 0.7 0.4]}, 'ScaleColorLimits', [0 20; 20 50; 50 100]);
uilabel(pe, 'Text', 'Vitesse des roues (rad/s)', 'Position', [12 268 290 22], 'FontWeight', 'bold');
roues = gobjects(1, 4);
for k = 1:4
    uilabel(pe, 'Text', sprintf('Roue %d', k), 'Position', [12 238 - 42 * (k - 1) 55 22]);
    roues(k) = uigauge(pe, 'linear', 'Position', [70 228 - 42 * (k - 1) 235 40], 'Limits', [0 450], ...
        'ScaleColors', {[0.85 0.3 0.2], [0.3 0.7 0.4], [0.85 0.3 0.2]}, 'ScaleColorLimits', [0 60; 60 400; 400 450]);
end
uilabel(pe, 'Text', 'Centre de masse par rapport au pivot', 'Position', [12 50 300 22], 'FontWeight', 'bold');
lab_deseq = uilabel(pe, 'Text', '-', 'Position', [12 8 300 40], 'WordWrap', 'on');

% ------------------------------------------------------------------ souris et clavier
fig.WindowButtonDownFcn = @appui;
fig.WindowButtonMotionFcn = @mouvement;
fig.WindowButtonUpFcn = @lacher;
fig.WindowKeyPressFcn = @touche;
fig.WindowKeyReleaseFcn = @touche_relachee;

% ------------------------------------------------------------------ échange avec le modèle
pilotage_banc('scenario', []);
pilotage_banc('actif', true);
pilotage_banc('abonner', @recevoir);
regler([0 0]);
minuterie = timer('Period', 0.5, 'ExecutionMode', 'fixedSpacing', 'BusyMode', 'drop', 'TimerFcn', @(~, ~) statut());
start(minuterie);
statut();

app = struct('figure', fig, 'regler_manche', @regler, 'lacher', @() lacher([], []), 'pousser', @pousser, ...
    'recevoir', @recevoir, 'demarrer', @() demarrer([], []), 'arreter', @() arreter([], []), 'fermer', @() fermer([], []));

% ================================================================== manche
    function regler(p)
        p = p(:).';
        if norm(p) > 1, p = p / norm(p); end
        manche = p;
        bouton.XData = p(1); bouton.YData = p(2);
        roulis = -p(2) * A; tangage = p(1) * A;             % +X baisse si le tangage est positif, +Y baisse si le roulis est négatif
        pilotage_banc('manche', roulis, tangage);
        lab_manche.Text = sprintf('Demandé : roulis %s°, tangage %s°', virgule(roulis, '%+.1f'), virgule(tangage, '%+.1f'));
    end

    function amplitude(v)
        A = round(v);
        curseur.Value = A;
        lab_amp.Text = sprintf('%d°', A);
        regler(manche);
    end

    function appui(~, ~)
        p = pad.CurrentPoint(1, 1:2);
        if all(abs(p) <= 1.25)
            glisse = true;
            regler(p);
        end
    end

    function mouvement(~, ~)
        if glisse
            regler(pad.CurrentPoint(1, 1:2));
        end
    end

    function lacher(~, ~)
        if glisse
            glisse = false;
            if ~garder.Value, regler([0 0]); end
        end
    end

    function touche(~, ev)
        if ~isfield(fleches, fleche_de(ev.Key)), return, end
        fleches.(fleche_de(ev.Key)) = 1;
        regler([fleches.droite - fleches.gauche, fleches.haut - fleches.bas]);
    end

    function touche_relachee(~, ev)
        if ~isfield(fleches, fleche_de(ev.Key)), return, end
        fleches.(fleche_de(ev.Key)) = 0;
        p = [fleches.droite - fleches.gauche, fleches.haut - fleches.bas];
        if any(p) || ~garder.Value, regler(p); end
    end

    function n = fleche_de(k)
        switch k
            case 'uparrow', n = 'haut';
            case 'downarrow', n = 'bas';
            case 'leftarrow', n = 'gauche';
            case 'rightarrow', n = 'droite';
            otherwise, n = 'autre';
        end
    end

% ================================================================== poussées
    function pousser(cote)
        F = force.Value;
        switch cote                                         % appuyer vers le bas sur un côté
            case '+X', c = [0; F];                          % +X baisse : couple de tangage positif
            case '-X', c = [0; -F];
            case '+Y', c = [-F; 0];                         % +Y baisse : couple de roulis négatif
            case '-Y', c = [F; 0];
        end
        pilotage_banc('pousser', c, 0.2);
        lab_poussee.Text = sprintf('Poussée sur le côté %s : %s N.m', cote, virgule(F, '%.3f'));
    end

% ================================================================== simulation
    function demarrer(~, ~)
        try
            if ~bdIsLoaded(mdl), load_system(fullfile(dossier, [mdl '.slx'])); end
            if ~strcmp(get_param(mdl, 'SimulationStatus'), 'stopped'), return, end
            set_param([mdl '/Procédé'], 'LabelModeActiveChoice', jumeau.Value);
            set_param([mdl '/Pupitre/Mode : manuel (haut) ou commande (bas)'], 'sw', '0');
            set_param([mdl '/Pupitre/Marche (haut) ou arrêt (bas)'], 'sw', num2str(double(moteurs.Value)));
            stop_origine = get_param(mdl, 'StopTime');
            rythme_origine = get_param(mdl, 'EnablePacing');
            % temps réel : c'est pilotage_banc qui cale la simulation sur l'horloge, le rythme de Simulink la ralentissait
            set_param(mdl, 'StopTime', num2str(duree.Value), 'EnablePacing', 'off');
            pilotage_banc('rythme', true);
            pilotage_banc('actif', suivre.Value);
            recu = false;
            vu_en_cours = false;
            t_lance = tic;
            lance_ici = true;
            set_param(mdl, 'SimulationCommand', 'start');
            message.Text = sprintf(['Simulation lancée avec le jumeau %s. Le banc est tenu 2 s, puis la commande le prend en main. ' ...
                'Pousse le manche pour l''incliner.'], jumeau.Value);
        catch err
            lance_ici = false;
            remettre();
            message.Text = ['Impossible de démarrer : ' err.message];
        end
        statut();
    end

    function remettre()
        % Rend au modèle sa durée et son rythme d'avant le lancement par l'interface.
        pilotage_banc('rythme', false);
        try
            if ~isempty(stop_origine), set_param(mdl, 'StopTime', stop_origine); end
            if ~isempty(rythme_origine), set_param(mdl, 'EnablePacing', rythme_origine); end
        catch
        end
        stop_origine = ''; rythme_origine = '';
    end

    function arreter(~, ~)
        try
            set_param(mdl, 'SimulationCommand', 'stop');
        catch
        end
        statut();
    end

    function marche(~, ev)
        try
            set_param([mdl '/Pupitre/Marche (haut) ou arrêt (bas)'], 'sw', num2str(double(ev.Value)));
            if ev.Value
                message.Text = 'Moteurs en marche.';
            else
                message.Text = 'Moteurs coupés : les ESC reçoivent le neutre, les roues ralentissent et le banc n''est plus tenu.';
            end
        catch err
            message.Text = err.message;
        end
    end

    function statut()
        if ~isvalid(fig), return, end
        try
            s = get_param(mdl, 'SimulationStatus');
        catch
            s = 'stopped';
        end
        en_cours = ~strcmp(s, 'stopped');
        if en_cours, vu_en_cours = true; end
        b_demarrer.Enable = matlab.lang.OnOffSwitchState(~en_cours);
        b_arreter.Enable = matlab.lang.OnOffSwitchState(en_cours);
        jumeau.Enable = matlab.lang.OnOffSwitchState(~en_cours);
        if en_cours
            lampe.Color = [0.3 0.75 0.4];
            lab_statut.Text = sprintf('En cours (jumeau %s)', get_param([mdl '/Procédé'], 'LabelModeActiveChoice'));
        else
            lampe.Color = [0.6 0.6 0.6];
            lab_statut.Text = 'Arrêtée';
            if lance_ici && (vu_en_cours || toc(t_lance) > 3)     % la simulation lancée par l'interface est finie
                if ~recu
                    message.Text = ['La simulation s''est arrêtée sans envoyer de données. Avec Webots : ouvre le monde ' ...
                        'banc_stabilisation.wbt et attends « jumeau Webots prêt » avant Démarrer. Le détail est dans le ' ...
                        'Diagnostic Viewer de Simulink.'];
                else
                    message.Text = 'Simulation terminée.';
                end
                remettre();
                lance_ici = false;
            end
        end
    end

% ================================================================== affichage
    function recevoir(d)
        % Chaque modification d'un élément de la fenêtre coûte du temps de calcul à la simulation : on ne touche qu'à ce
        % qui change, et les jauges ne sont rafraîchies qu'un envoi sur trois.
        if ~isvalid(fig), return, end
        if isempty(d), statut(); return, end
        recu = true;
        n_recus = n_recus + 1;
        texte(lab_roulis, [virgule(d.angles(1), '%+.1f') '°']);
        texte(lab_tangage, [virgule(d.angles(2), '%+.1f') '°']);
        texte(lab_roulis_ref, ['demandé ' virgule(d.reference(1), '%+.1f') '°']);
        texte(lab_tangage_ref, ['demandé ' virgule(d.reference(2), '%+.1f') '°']);
        u = max(-1.2, min(1.2, d.angles(2) / A)); v = max(-1.2, min(1.2, -d.angles(1) / A));
        if abs(u - mesure.XData) + abs(v - mesure.YData) > 0.004
            set(mesure, 'XData', u, 'YData', v);
        end
        if mod(n_recus, 3) == 1
            jauge(reserve, round(100 * max(0, min(1, d.reserve))));
            for j = 1:4
                jauge(roues(j), round(max(0, min(450, d.roues(j)))));
            end
            texte(lab_deseq, sprintf('X : %s mm    Y : %s mm (mesuré quand le banc est immobile)', ...
                virgule(d.desequilibre(1), '%+.2f'), virgule(d.desequilibre(2), '%+.2f')));
            texte(lab_t, sprintf('t = %s s', virgule(d.t, '%.0f')));
        end
        drawnow limitrate
    end

    function texte(h, s)
        if ~strcmp(h.Text, s), h.Text = s; end
    end

    function jauge(h, x)
        if h.Value ~= x, h.Value = x; end
    end

% ================================================================== fermeture
    function fermer(~, ~)
        try
            if lance_ici && ~strcmp(get_param(mdl, 'SimulationStatus'), 'stopped')
                set_param(mdl, 'SimulationCommand', 'stop');
            end
        catch
        end
        pilotage_banc('actif', false);
        pilotage_banc('abonner', []);
        remettre();
        try, stop(minuterie); delete(minuterie); catch, end
        delete(fig);
    end
end

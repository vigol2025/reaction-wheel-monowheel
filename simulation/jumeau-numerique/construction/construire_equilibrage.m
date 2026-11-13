function construire_equilibrage(fichier)
% Met le jumeau Simscape au niveau de la CAO équilibrée, sans régénérer le modèle.
% À lancer après preparer_cao.py (qui écrit cao_jumeau.json et les STL de geometrie/).
%
% Ce que le script fait :
%   - met à jour la masse, le centre de masse et l'inertie des pièces déjà posées (dispositif et paliers) ;
%   - pose les pièces nouvelles du dispositif : 4 tiges filetées d'équilibrage, écrous de serrage, écrous de réglage ;
%   - ajoute le pivot d'équilibre aux positions possibles et en fait la position de départ ;
%   - met à jour les masses et inerties utilisées par la commande ;
%   - coupe la désaturation par défaut : sur un banc équilibré, se pencher ne décharge plus les roues.

ici = fileparts(mfilename('fullpath'));
if nargin < 1
    fichier = fullfile(fileparts(ici), 'jumeau_banc_rw.slx');
end
[~, nom] = fileparts(fichier);
cao = jsondecode(fileread(fullfile(ici, 'cao_jumeau.json')));
load_system(fichier);
m = [nom '/Procédé/Jumeau Simscape/Mécanique (CAO version 3)'];
pieces(cao, 'dispositif', [m '/Dispositif (corps, étage, électronique, câblage)']);
pieces(cao, 'paliers', [m '/Paliers de tangage']);
parametres(nom, cao);
save_system(nom, fichier);
close_system(nom, 0);
fprintf('équilibrage en place : %s\n', fichier);
end

function pieces(cao, cle, g)
I = cao.instances(strcmp({cao.instances.groupe}, cle));
port = get_param([g '/F'], 'PortHandles');
existants = find_system(g, 'SearchDepth', 1, 'regexp', 'on', 'Name', '^Pose ');
k = numel(find_system(g, 'SearchDepth', 1, 'Type', 'block')) - 2 - numel(existants);   % pièces déjà posées (ni le port, ni les poses)
maj = 0; neuf = 0;
for i = 1:numel(I)
    in = I(i);
    lab = strrep(in.nom, '/', ' ');
    s = cao.solides.(matlab.lang.makeValidName(in.solide));
    fs = [g '/' lab];
    if isempty(find_system(g, 'SearchDepth', 1, 'Name', lab))
        k = k + 1; neuf = neuf + 1;
        col = floor((k - 1) / 8); lig = mod(k - 1, 8);
        x = 120 + 560 * col; y = 40 + 65 * lig;
        add_block('sm_lib/Body Elements/File Solid', fs, 'Position', [x + 260 y x + 310 y + 40], 'Orientation', 'left');
        rt = [g '/Pose ' lab];
        add_block('sm_lib/Frames and Transforms/Rigid Transform', rt, 'Position', [x y x + 50 y + 40]);
        add_line(g, port.RConn(1), get_param(rt, 'PortHandles').LConn(1), 'autorouting', 'smart');
        add_line(g, get_param(rt, 'PortHandles').RConn(1), get_param(fs, 'PortHandles').RConn(1), 'autorouting', 'smart');
    else
        maj = maj + 1;
    end
    rt = [g '/Pose ' lab];                 % pose de la pièce, mise à jour aussi quand elle a bougé dans la CAO
    if ~isempty(find_system(g, 'SearchDepth', 1, 'Name', ['Pose ' lab]))
        set_param(rt, 'RotationMethod', 'RotationMatrix', 'RotationMatrix', mat2str(round(in.R, 10)), ...
            'TranslationMethod', 'Cartesian', 'TranslationCartesianOffset', mat2str(round(in.t_mm(:)', 6)), ...
            'TranslationCartesianOffsetUnits', 'mm');
    end
    Ig = s.I;
    rgb = sscanf(s.couleur(2:end), '%2x%2x%2x')' / 255;
    set_param(fs, 'ExtGeomFileName', s.stl, 'UnitType', 'Custom', 'ExtGeomFileUnits', 'mm', ...
        'InertiaType', 'Custom', 'Mass', num2str(s.m, 8), 'MassUnits', 'kg', ...
        'CenterOfMass', mat2str(s.G', 8), 'CenterOfMassUnits', 'm', ...
        'MomentsOfInertia', mat2str([Ig(1, 1) Ig(2, 2) Ig(3, 3)], 8), 'MomentsOfInertiaUnits', 'kg*m^2', ...
        'ProductsOfInertia', mat2str([Ig(2, 3) Ig(3, 1) Ig(1, 2)], 8), 'ProductsOfInertiaUnits', 'kg*m^2', ...
        'GraphicType', 'FromGeometry', 'GraphicVisPropType', 'SimpleVisualProperties', ...
        'GraphicDiffuseColor', mat2str(round(rgb, 3)), 'GraphicOpacity', '1');
    set_param(fs, 'Description', sprintf('Pièce CAO : %s (%s)\nMasse %.2f g : %s.\nCentre de masse et inertie : calculés sur la géométrie de la CAO.', ...
        in.nom, in.solide, s.m * 1000, s.source));
end
fprintf('%s : %d pièces mises à jour, %d pièces ajoutées\n', cle, maj, neuf);
end

function parametres(nom, cao)
mws = get_param(nom, 'ModelWorkspace');
code = mws.MATLABCode;
c = cao.controle;
zeq = c.z_pivot_equilibre_mm;
liste = strtrim(sprintf('%g ', [zeq; cao.z_pivots(cao.z_pivots ~= zeq)]));
r = {'(?m)^pivot_mm = [^\n]*', sprintf('pivot_mm = %g;              %% position du pivot de tangage sur le corps : %s mm (%g : banc équilibré, rangée +24 et paliers remontés de %g mm)', ...
        zeq, strrep(liste, ' ', ', '), zeq, zeq - cao.z_pivot_cao);
     '(?m)^assert\(any\(pivot_mm == [^\n]*', sprintf('assert(any(pivot_mm == [%s]), ''pivot_mm : %s'');', liste, strrep(liste, ' ', ', '));
     '(?m)^m_disp = [^;]*;', sprintf('m_disp = %.4f;', c.m_disp);
     '(?m)^zG_disp = [^;]*;', sprintf('zG_disp = %.3fe-3;', c.G_disp(3) * 1000);
     '(?m)^Ixx_disp_24 = [^;]*;', sprintf('Ixx_disp_24 = %.4fe-3;', c.I_disp_pivot(1, 1) * 1000);
     '(?m)^Iyy_disp_24 = [^;]*;', sprintf('Iyy_disp_24 = %.4fe-3;', c.I_disp_pivot(2, 2) * 1000);
     '(?m)^m_croix = [^;]*;', sprintf('m_croix = %.4f;', c.m_croix);
     '(?m)^Ixx_croix = [^;]*;', sprintf('Ixx_croix = %.3fe-4;', c.Ixx_croix_pivot * 1e4);
     '(?m)^desat_active = [^;]*;', 'desat_active = 0;';
     '(?m)^k_desat = [^;]*;', 'k_desat = desat_active.*sign(mgh_axe + (mgh_axe == 0))./(max(abs(mgh_axe), 1e-3)*T_desat);'};
for k = 1:size(r, 1)
    assert(~isempty(regexp(code, r{k, 1}, 'once')), r{k, 1});
    code = regexprep(code, r{k, 1}, regexptranslate('escape', r{k, 2}), 'once');
end
mws.MATLABCode = code;
mws.reload;
end

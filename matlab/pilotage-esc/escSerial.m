function y = escSerial(throttle, stopSignal)
% escSerial: envoie throttle (T,...) et stop (X) à l'ESP32 via serialport
% Retourne y=0 pour satisfaire Simulink (sortie bidon)
%
% Correction: keep-alive pour éviter le failsafe ESP32 quand le slider ne bouge pas.

y = 0;  % valeur par défaut (valide même si return)

PORT = "COM8";
BAUD = 115200;

persistent sp lastSent wasStopped tLast lastKeepAlive
if isempty(sp)
    delete(serialportfind);
    sp = serialport(PORT, BAUD);
    configureTerminator(sp, "LF");
    flush(sp);

    lastSent      = single(-1);
    wasStopped    = false;
    tLast         = tic;
    lastKeepAlive = tic;
end

% ---- STOP prioritaire ----
if stopSignal ~= 0
    if ~wasStopped
        write(sp, 'X\n', 'char');   % envoi stop
        wasStopped = true;
    end
    return; % y déjà défini
else
    wasStopped = false;
end

% ---- Throttle ----
throttle = max(0, min(1, throttle));
throttle = single(throttle);

% limiter fréquence d'appel (20 Hz)
SEND_PERIOD = 0.05;
if toc(tLast) < SEND_PERIOD
    return;
end
tLast = tic;

% ---- Keep-alive (anti failsafe) ----
% Ton ESP32 a failsafeMs=500 ms => il faut renvoyer avant 0.5s.
KEEPALIVE_S = 0.20;  % secondes (0.2s = marge confortable)

needSend = abs(throttle - lastSent) > 0.002;
needKeepAlive = toc(lastKeepAlive) >= KEEPALIVE_S;

if needSend || needKeepAlive
    cmd = sprintf('T,%.3f\n', throttle);
    write(sp, cmd, 'char');
    lastSent = throttle;
    lastKeepAlive = tic;
end

% y reste 0
end


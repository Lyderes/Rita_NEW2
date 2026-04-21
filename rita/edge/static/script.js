// ---------- EL RELOJ ----------
function updateClock() {
    const now = new Date();
    let h = now.getHours();
    let m = now.getMinutes();
    const ampm = h >= 12 ? 'PM' : 'AM';
    h = h % 12 || 12;
    m = m < 10 ? '0' + m : m;
    document.getElementById('clock').innerText = `${h}:${m} ${ampm}`;
}
setInterval(updateClock, 1000);
updateClock();

// ---------- EL CLIMA (Open-Meteo) ----------
async function updateWeather() {
    try {
        // Coordenadas de ejemplo (Madrid)
        const lat = 40.4165;
        const lon = -3.7026;
        const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`);
        const data = await res.json();
        const temp = Math.round(data.current_weather.temperature);
        const isDay = data.current_weather.is_day;
        
        let icon = '<i class="fas fa-sun" style="color:#ffcc00"></i>';
        if (!isDay) icon = '<i class="fas fa-moon" style="color:#a0a0a0"></i>';
        if (data.current_weather.weathercode > 3) icon = '<i class="fas fa-cloud" style="color:#ffffff"></i>';

        document.getElementById('weather').innerHTML = `${icon} ${temp}°C | MAD`;
    } catch(e) {
        document.getElementById('weather').innerHTML = `<i class="fas fa-cloud"></i> --° | --`;
    }
}
updateWeather();
setInterval(updateWeather, 600000);

// ---------- LOGICA DEL PIN (EMERGENCIA) ----------
let pin = "";
function pressNum(n) {
    if(pin.length < 4) {
        pin += n;
        updatePinDisplay();
    }
    if(pin === "0000") {
        fetch("/api/exit", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({code: "0000"})
        });
        document.getElementById('state-label').innerText = "APAGANDO KIOSKO";
        hideNumpad();
        // Fallback visual
        setTimeout(() => { document.body.innerHTML = "<h1 style='color:orange; text-align:center; margin-top:20%; font-family:Orbitron;'>SISTEMA CERRADO</h1>"; }, 1500);
    }
}
function clearPin() { pin = ""; updatePinDisplay(); }
function updatePinDisplay() {
    let display = "";
    for(let i=0; i<4; i++) display += (i < pin.length) ? "●" : "-";
    document.getElementById('pin-display').innerText = display;
}
function hideNumpad() {
    document.getElementById('numpad-modal').classList.add('hidden');
    pin = ""; updatePinDisplay();
}

// Abrir el Numpad al tocar la batería/Logo R
document.getElementById('exit-btn').addEventListener('click', () => {
    document.getElementById('numpad-modal').classList.remove('hidden');
});

// ---------- SINCRONIZACIÓN DE DATOS RITA ----------
// Variables para apuntar los parámetros de las ondas
let targetAmplitude = 15;
let targetSpeed = 0.015;

setInterval(async () => {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        // Pinta los textos dinámicos
        document.getElementById('user-text').innerText = data.user_text ? data.user_text + "  " : "¿En qué puedo ayudarte?";
        document.getElementById('rita-text').innerText = data.rita_text || "";
        
        // Mapea el estado a colores y avatar (Tonos suaves azules)
        if(data.status === 'esperando') {
            stateLabel.innerText = "STANDBY";
            stateLabel.style.color = "#7dd3fc";
            stateLabel.style.textShadow = "none";
            setState('idle');
        } else if(data.status === 'escuchando') {
            stateLabel.innerText = "ESCUCHANDO";
            stateLabel.style.color = "#34d399";
            stateLabel.style.textShadow = "0 0 15px rgba(52, 211, 153, 1)";
            setState('listening');
        } else if(data.status === 'pensando') {
            stateLabel.innerText = "PENSANDO";
            stateLabel.style.color = "#a78bfa";
            stateLabel.style.textShadow = "0 0 20px rgba(167, 139, 250, 0.8)";
            setState('thinking');
        } else if(data.status === 'hablando') {
            stateLabel.innerText = "HABLANDO";
            stateLabel.style.color = "#60a5fa";
            stateLabel.style.textShadow = "0 0 25px rgba(96, 165, 250, 1)";
            setState('speaking');
        } else if(data.status === 'contenta' || data.emotion === 'happy') {
            stateLabel.innerText = "FELIZ";
            stateLabel.style.color = "#f472b6";
            stateLabel.style.textShadow = "0 0 20px rgba(244, 114, 182, 0.8)";
            setState('happy');
        } else if(data.status === 'triste' || data.emotion === 'sad') {
            stateLabel.innerText = "TRISTE";
            stateLabel.style.color = "#94a3b8";
            stateLabel.style.textShadow = "none";
            setState('sad');
        } else if(data.status === 'sorprendida' || data.emotion === 'surprised') {
            stateLabel.innerText = "SORPRENDIDA";
            stateLabel.style.color = "#fde047";
            stateLabel.style.textShadow = "0 0 20px rgba(253, 224, 71, 0.8)";
            setState('surprised');
        }

    } catch(e) {
        document.getElementById('state-label').innerText = "DESCONECTADO";
        setState('sad');
    }
}, 300);

// ---------- LOGICA DE AVATAR (CARA RITA) ----------
let currentState = 'idle';
let speakingInterval = null;
let isSpeaking = false;

function setState(state) {
    if (currentState === state) return;
    currentState = state;
    document.body.className = `state-${state}`;
    
    if (state === 'speaking') {
       startSpeakingAnimation();
    } else {
       stopSpeakingAnimation();
    }
}

function startSpeakingAnimation() {
    if (isSpeaking) return;
    isSpeaking = true;
    speakingInterval = setInterval(() => {
        const mouth = document.getElementById('mouth');
        if (currentState === 'speaking') {
            const height = 10 + Math.random() * 25;
            const width = 30 + Math.random() * 15;
            mouth.style.height = `${height}px`;
            mouth.style.width = `${width}px`;
            mouth.style.borderRadius = `${10 + Math.random()*20}px`;
        }
    }, 120);
}

function stopSpeakingAnimation() {
    isSpeaking = false;
    clearInterval(speakingInterval);
    document.getElementById('mouth').style = ''; 
}

function blink() {
    if (currentState === 'happy' || currentState === 'surprised') {
        setTimeout(blink, 2000 + Math.random() * 3000);
        return; 
    }
    const eyeL = document.getElementById('eyeL');
    const eyeR = document.getElementById('eyeR');
    if (eyeL && eyeR) {
        eyeL.classList.add('blink');
        eyeR.classList.add('blink');
        setTimeout(() => {
            eyeL.classList.remove('blink');
            eyeR.classList.remove('blink');
        }, 150);
    }
    setTimeout(blink, 2500 + Math.random() * 4500);
}
setTimeout(blink, 1000);

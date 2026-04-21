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
        
        const stateLabel = document.getElementById('state-label');

        // Mapea el estado a colores y animación
        if(data.status === 'esperando') {
            stateLabel.innerText = "STANDBY";
            stateLabel.style.color = "#777777";
            stateLabel.style.textShadow = "none";
            targetAmplitude = 15; // Ondas en reposo
            targetSpeed = 0.005;
        } else if(data.status === 'escuchando') {
            stateLabel.innerText = "LISTENING";
            stateLabel.style.color = "#ff6600";
            stateLabel.style.textShadow = "0 0 15px rgba(255, 102, 0, 1)";
            targetAmplitude = 80;
            targetSpeed = 0.035;
        } else if(data.status === 'pensando') {
            stateLabel.innerText = "PROCESSING";
            stateLabel.style.color = "#ffbb66";
            stateLabel.style.textShadow = "0 0 20px rgba(255, 180, 50, 0.8)";
            targetAmplitude = 40;
            targetSpeed = 0.02;
        } else if(data.status === 'hablando') {
            stateLabel.innerText = "SPEAKING";
            stateLabel.style.color = "#ff4400";
            stateLabel.style.textShadow = "0 0 25px rgba(255, 50, 0, 1)";
            targetAmplitude = 140; // Ondas gigantes
            targetSpeed = 0.05;
        }

    } catch(e) {
        document.getElementById('state-label').innerText = "DISCONNECTED";
        targetAmplitude = 5;
        targetSpeed = 0.001;
    }
}, 300);

// ---------- CANVAS WAVES (MAGIA VISUAL) ----------
const canvas = document.getElementById('waves-canvas');
const ctx = canvas.getContext('2d');

let width, height;
function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
}
window.addEventListener('resize', resize);
resize();

let currentAmplitude = 15;
let currentSpeed = 0.015;
let time = 0;

function animate() {
    // Transición suave entre estados (aceleración/desaceleración orgánica)
    currentAmplitude += (targetAmplitude - currentAmplitude) * 0.08;
    currentSpeed += (targetSpeed - currentSpeed) * 0.08;
    time += currentSpeed;

    // Limpiar frame
    ctx.clearRect(0, 0, width, height);
    
    // Dibujamos 3 capas de ondas superpuestas al estilo Osciloscopio Sci-Fi
    // parameters: freqMult, waveLength, ampMultiplier, offset, color, lineWidth, glow
    drawWave(1.0, 0.008, currentAmplitude * 1.0, 0, 'rgba(255, 100, 0, 0.8)', 4, 20); // Principal
    drawWave(1.3, 0.012, currentAmplitude * 1.5, Math.PI, 'rgba(255, 150, 50, 0.5)', 2, 10); // Cruzada ràpida
    drawWave(0.8, 0.005, currentAmplitude * 0.7, Math.PI/2, 'rgba(255, 50, 0, 0.3)', 6, 30); // Lenta de fondo

    requestAnimationFrame(animate);
}

function drawWave(freqMult, waveLength, amp, phaseOffset, color, lineWidth, glow) {
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    
    for (let x = 0; x < width; x += 4) {
        // Taper hace que las ondas mueran en los bordes como en la foto
        const taper = Math.sin((Math.PI * x) / width);
        
        // Sumamos dos funciones seno para que parezca ruido de audio real
        const mainWave = Math.sin(x * waveLength + time * freqMult + phaseOffset);
        const secondaryWave = Math.sin(x * (waveLength*2.5) - time);
        
        const y = (mainWave + secondaryWave * 0.3) * amp * taper;
        
        // Centramos las ondas un poco más arriba visualmente (offset Y)
        ctx.lineTo(x, (height / 2) - 40 + y);
    }
    
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.shadowBlur = glow;
    ctx.shadowColor = color;
    // Truco performance para canvas: renderizado más fluido en Raspberry
    ctx.lineJoin = 'round';
    ctx.stroke();
}

// Iniciar Motor
animate();

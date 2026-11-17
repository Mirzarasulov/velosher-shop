document.addEventListener('DOMContentLoaded', () => {
    
    // --- 1. БЛЕСТКИ ---
    const sparklesContainer = document.getElementById('sparkles-container');
    
    function createSparkle() {
        const sparkle = document.createElement('div');
        sparkle.classList.add('sparkle');
        sparkle.style.left = Math.random() * 100 + 'vw';
        // Размер блестки от 2 до 5px (чуть крупнее)
        const size = Math.random() * 3 + 2 + 'px'; 
        sparkle.style.width = size;
        sparkle.style.height = size;
        sparkle.style.animationDuration = Math.random() * 8 + 6 + 's'; 
        
        sparklesContainer.appendChild(sparkle);
        
        setTimeout(() => { sparkle.remove(); }, 14000);
    }
    
    setInterval(createSparkle, 500);


    // --- 2. ОТКРЫТИЕ КОНВЕРТА ---
    const envelope = document.getElementById('envelope');
    const envelopeScreen = document.getElementById('envelope-screen');
    const mainContent = document.getElementById('main-content');
    const musicPlayer = document.getElementById('musicPlayer');
    const body = document.body;

    envelope.addEventListener('click', () => {
        envelope.classList.add('open');

        setTimeout(() => {
            envelopeScreen.classList.add('hide');
            body.classList.add('opened');
            
            setTimeout(() => {
                mainContent.classList.remove('hidden');
                musicPlayer.style.display = 'flex';
                
                if(audio) {
                    audio.play().catch(e => console.log("Аудио файл music.mp3 не найден"));
                    playBtn.innerText = "II";
                    isPlaying = true;
                }

                const firstPage = document.querySelectorAll('.page')[0];
                firstPage.classList.add('visible');

            }, 300);

        }, 600); 
    });


    // --- 3. АНИМАЦИЯ СТРАНИЦ ---
    const pages = document.querySelectorAll('.page');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, { threshold: 0.3 });

    pages.forEach(page => observer.observe(page));


    // --- 4. ТАЙМЕР ---
    const weddingDate = new Date("Dec 10, 2026 18:00:00").getTime();

    const updateTimer = setInterval(() => {
        const now = new Date().getTime();
        const distance = weddingDate - now;

        if (distance < 0) {
            clearInterval(updateTimer);
            return;
        }

        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);

        document.getElementById("days").innerText = days < 10 ? "0" + days : days;
        document.getElementById("hours").innerText = hours < 10 ? "0" + hours : hours;
        document.getElementById("minutes").innerText = minutes < 10 ? "0" + minutes : minutes;
        document.getElementById("seconds").innerText = seconds < 10 ? "0" + seconds : seconds;
    }, 1000);


    // --- 5. МОДАЛЬНОЕ ОКНО КАРТ ---
    const openMapBtn = document.getElementById('openMapBtn');
    const mapModal = document.getElementById('mapModal');
    const closeBtn = document.querySelector('.close-btn');

    openMapBtn.addEventListener('click', () => {
        mapModal.classList.add('active');
    });

    closeBtn.addEventListener('click', () => {
        mapModal.classList.remove('active');
    });

    window.addEventListener('click', (e) => {
        if (e.target === mapModal) {
            mapModal.classList.remove('active');
        }
    });


    // --- 6. МУЗЫКА ---
    const playBtn = document.getElementById('playBtn');
    let audio = new Audio('music.mp3'); 
    let isPlaying = false;
    audio.loop = true;

    playBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!isPlaying) {
            audio.play().catch(e => console.log("Аудио не найдено"));
            playBtn.innerText = "II";
            isPlaying = true;
        } else {
            audio.pause();
            playBtn.innerText = "▶";
            isPlaying = false;
        }
    });
});
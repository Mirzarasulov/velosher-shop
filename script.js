document.addEventListener('DOMContentLoaded', () => {

    // --- 1. БЛЕСТКИ ---
    const sparklesContainer = document.getElementById('sparkles-container');
    function createSparkle() {
        const sparkle = document.createElement('div');
        sparkle.classList.add('sparkle');
        sparkle.style.left = Math.random() * 100 + 'vw';
        const size = Math.random() * 3 + 2 + 'px';
        sparkle.style.width = size;
        sparkle.style.height = size;
        sparkle.style.animationDuration = Math.random() * 8 + 6 + 's';
        sparklesContainer.appendChild(sparkle);
        setTimeout(() => sparkle.remove(), 14000);
    }
    setInterval(createSparkle, 500);

    // --- 2. МУЗЫКА (МАКСИМАЛЬНЫЙ ОБХОД) ---
    const bgMusic = document.getElementById('bg-music');
    const playBtn = document.getElementById('playBtn');
    const musicPlayer = document.getElementById('musicPlayer');
    
    // Функция разблокировки аудио (Web Audio API)
    function unlockAudio() {
        if (bgMusic && bgMusic.paused) {
            bgMusic.play().then(() => {
                // Если заиграло - отключаем слушатели
                document.removeEventListener('click', unlockAudio);
                document.removeEventListener('touchstart', unlockAudio);
                document.removeEventListener('keydown', unlockAudio);
            }).catch(e => {
                console.log("Ждем взаимодействия...");
            });
        }
    }

    // Вешаем слушатели на первый клик/тап в любом месте страницы
    document.addEventListener('click', unlockAudio);
    document.addEventListener('touchstart', unlockAudio);
    document.addEventListener('keydown', unlockAudio);

    // Обновление UI кнопки
    function updateMusicUI() {
        if (bgMusic.paused) {
            playBtn.innerText = '▶';
            musicPlayer.classList.add('paused');
        } else {
            playBtn.innerText = 'II';
            musicPlayer.classList.remove('paused');
        }
    }
    bgMusic.addEventListener('play', updateMusicUI);
    bgMusic.addEventListener('pause', updateMusicUI);

    // --- 3. ОТКРЫТИЕ КОНВЕРТА ---
    const envelope = document.getElementById('envelope');
    const envelopeScreen = document.getElementById('envelope-screen');
    const mainContent = document.getElementById('main-content');
    const body = document.body;
    let opened = false;

    envelope.addEventListener('click', () => {
        if (opened) return;
        opened = true;

        envelope.classList.add('open');
        body.classList.add('opened');

        // Стартуем музыку
        bgMusic.volume = 0.7;
        bgMusic.play().catch(() => {
            console.log("Браузер заблокировал автоплей, ждем тапа");
        });

        musicPlayer.style.display = 'flex';

        setTimeout(() => {
            envelopeScreen.classList.add('hide');
        }, 600);

        setTimeout(() => {
            mainContent.classList.remove('hidden');
            const firstPage = document.querySelector('.page');
            if (firstPage) firstPage.classList.add('visible');
        }, 900);
    });

    // --- 4. АНИМАЦИЯ СТРАНИЦ ---
    const pages = document.querySelectorAll('.page');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) entry.target.classList.add('visible');
        });
    }, { threshold: 0.3 });
    pages.forEach(page => observer.observe(page));

    // --- 5. ТАЙМЕР ---
    const weddingDate = new Date('2026-12-10T18:00:00').getTime();
    const pad = n => n < 10 ? '0' + n : String(n);

    function updateTimer() {
        const distance = weddingDate - Date.now();
        if (distance <= 0) {
            ['days', 'hours', 'minutes', 'seconds'].forEach(id => {
                document.getElementById(id).innerText = '00';
            });
            return;
        }
        document.getElementById('days').innerText = pad(Math.floor(distance / 86400000));
        document.getElementById('hours').innerText = pad(Math.floor((distance % 86400000) / 3600000));
        document.getElementById('minutes').innerText = pad(Math.floor((distance % 3600000) / 60000));
        document.getElementById('seconds').innerText = pad(Math.floor((distance % 60000) / 1000));
    }
    updateTimer();
    setInterval(updateTimer, 1000);

    // --- 6. КАРТЫ ---
    const openMapBtn = document.getElementById('openMapBtn');
    const mapModal = document.getElementById('mapModal');
    const closeBtn = document.querySelector('.close-btn');

    openMapBtn.addEventListener('click', () => mapModal.classList.add('active'));
    closeBtn.addEventListener('click', () => mapModal.classList.remove('active'));
    mapModal.addEventListener('click', e => {
        if (e.target === mapModal) mapModal.classList.remove('active');
    });

    // --- 7. КНОПКА МУЗЫКИ ---
    playBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (bgMusic.paused) {
            bgMusic.play();
        } else {
            bgMusic.pause();
        }
    });

    // --- 8. СТРЕЛКИ ВНИЗ ---
    document.querySelectorAll('.scroll-down').forEach(btn => {
        btn.addEventListener('click', () => {
            mainContent.scrollBy({ top: window.innerHeight, behavior: 'smooth' });
        });
    });
});

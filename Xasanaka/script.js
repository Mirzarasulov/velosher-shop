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
        
        setTimeout(() => { sparkle.remove(); }, 14000);
    }
    
    setInterval(createSparkle, 500);


    // --- 2. МУЗЫКА (YOUTUBE API) ---
    // Загружаем API YouTube асинхронно
    let player;
    let isPlaying = false;
    
    const tag = document.createElement('script');
    tag.src = "https://www.youtube.com/iframe_api";
    const firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

    // Эта функция вызывается автоматически, когда API загрузится
    window.onYouTubeIframeAPIReady = function() {
        player = new YT.Player('youtube-player', {
            height: '0',
            width: '0',
            videoId: 'h6C1sava8us', // ID вашего трека
            playerVars: {
                'autoplay': 0, // Не включаем сразу
                'controls': 0,
                'loop': 1,
                'playlist': 'h6C1sava8us' // Нужно для зацикливания
            },
            events: {
                'onReady': onPlayerReady,
                'onStateChange': onPlayerStateChange
            }
        });
    };

    function onPlayerReady(event) {
        // Плеер готов, но музыка еще не играет
    }

    function onPlayerStateChange(event) {
        // Синхронизируем кнопку с состоянием плеера
        const playBtn = document.getElementById('playBtn');
        const musicPlayer = document.getElementById('musicPlayer');
        
        if (event.data == YT.PlayerState.PLAYING) {
            playBtn.innerText = "II";
            musicPlayer.classList.remove('paused');
            isPlaying = true;
        } else {
            playBtn.innerText = "▶";
            musicPlayer.classList.add('paused');
            isPlaying = false;
        }
    }

    // --- 3. ОТКРЫТИЕ КОНВЕРТА ---
    const envelope = document.getElementById('envelope');
    const envelopeScreen = document.getElementById('envelope-screen');
    const mainContent = document.getElementById('main-content');
    const musicPlayer = document.getElementById('musicPlayer');
    const body = document.body;

    envelope.addEventListener('click', () => {
        envelope.classList.add('open');

        // Включаем музыку (если плеер готов)
        if (player && typeof player.playVideo === 'function') {
            player.playVideo();
        } else {
            // Если плеер не успел загрузиться, пробуем еще раз через секунду
            setTimeout(() => {
                if (player && typeof player.playVideo === 'function') {
                    player.playVideo();
                }
            }, 1000);
        }

        setTimeout(() => {
            envelopeScreen.classList.add('hide');
            body.classList.add('opened');
            
            setTimeout(() => {
                mainContent.classList.remove('hidden');
                musicPlayer.style.display = 'flex'; // Показываем кнопку музыки
                
                const firstPage = document.querySelectorAll('.page')[0];
                firstPage.classList.add('visible');

            }, 300);

        }, 600); 
    });


    // --- 4. АНИМАЦИЯ СТРАНИЦ ---
    const pages = document.querySelectorAll('.page');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, { threshold: 0.3 });

    pages.forEach(page => observer.observe(page));


    // --- 5. ТАЙМЕР ---
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


    // --- 6. МОДАЛЬНОЕ ОКНО КАРТ ---
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


    // --- 7. КНОПКА ПАУЗЫ / ВОСПРОИЗВЕДЕНИЯ ---
    const playBtn = document.getElementById('playBtn');
    
    playBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        
        if (!player) return;

        if (isPlaying) {
            player.pauseVideo();
        } else {
            player.playVideo();
        }
    });
});

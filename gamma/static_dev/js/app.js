document.addEventListener('DOMContentLoaded', () => {
    const navItems = document.querySelectorAll('.nav-item');
    const navIndicator = document.querySelector('.nav-indicator');
    const views = document.querySelectorAll('.view');
    const pageTitle = document.getElementById('page-title');
    const pillNavItems = document.querySelectorAll('.nav-pill .nav-item');

    function isDesktop() {
        return window.innerWidth >= 768;
    }

    // Initialize indicator position
    function updateIndicator(activeItem) {
        if (!activeItem || !navIndicator) return;
        
        if (activeItem.closest('.nav-pill')) {
            const offsetL = activeItem.offsetLeft;
            const offsetT = activeItem.offsetTop;
            const width = activeItem.offsetWidth;
            const height = activeItem.offsetHeight;
            
            if (isDesktop()) {
                // Vertical Rail mode
                navIndicator.style.transform = `translateY(${offsetT}px)`;
                navIndicator.style.height = `${height}px`;
                navIndicator.style.width = 'auto'; // Width handled by CSS left/right
            } else {
                // Horizontal Pill mode
                navIndicator.style.transform = `translateX(${offsetL}px)`;
                navIndicator.style.width = `${width}px`;
                navIndicator.style.height = 'auto'; // Height handled by CSS top/bottom
            }
            navIndicator.style.opacity = '1';
        } else {
            // Profile clicked
            navIndicator.style.opacity = '0.5';
        }
    }

    // Update on resize
    window.addEventListener('resize', () => {
        const activeItem = document.querySelector('.nav-item.active');
        // Reset inline styles that might conflict
        navIndicator.style.width = '';
        navIndicator.style.height = '';
        navIndicator.style.transform = '';
        updateIndicator(activeItem);
    });

    // Set initial state
    document.fonts.ready.then(() => {
        const initialActive = document.querySelector('.nav-item.active');
        updateIndicator(initialActive);
    });

    // Navigation Click Handler
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            updateIndicator(item);

            const newTitle = item.getAttribute('data-title');
            if (newTitle) {
                pageTitle.style.opacity = '0';
                pageTitle.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    pageTitle.textContent = newTitle;
                    pageTitle.style.opacity = '1';
                    pageTitle.style.transform = 'translateY(0)';
                }, 150);
            }

            const targetId = item.getAttribute('data-target');
            views.forEach(view => {
                if (view.id === targetId) {
                    view.classList.add('active');
                } else {
                    view.classList.remove('active');
                }
            });

            const profileNav = document.querySelector('.nav-profile');
            if (targetId === 'view-profile') {
                profileNav.classList.add('active-bg');
            } else {
                profileNav.classList.remove('active-bg');
            }
        });
    });

    const bounceItems = document.querySelectorAll('.bounce');
    bounceItems.forEach(el => {
        el.addEventListener('click', () => {
            if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
                window.Telegram.WebApp.HapticFeedback.selectionChanged();
            }
        });
    });

    function initTelegram() {
        if (!window.Telegram || !window.Telegram.WebApp) return;
        const tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();
        
        const user = tg.initDataUnsafe?.user;
        if (user) {
            const profileName = document.getElementById('profile-name');
            const profileUserid = document.getElementById('profile-userid');
            const connectionUsername = document.getElementById('connection-username');
            const profileAvatar = document.getElementById('profile-avatar');

            const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ');
            if (profileName) {
                profileName.textContent = fullName || user.username || 'Пользователь Telegram';
            }

            if (profileUserid) {
                profileUserid.textContent = `ID: ${user.id}`;
            }

            if (connectionUsername) {
                const displayName = user.username ? `@${user.username}` : user.first_name;
                connectionUsername.textContent = displayName;
            }

            if (profileAvatar) {
                const initial = (user.first_name || user.username || 'U').charAt(0).toUpperCase();
                profileAvatar.innerHTML = `<span style="font-size: 28px; font-weight: 500;">${initial}</span>`;
            }
        }
    }

    initTelegram();
});

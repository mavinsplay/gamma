document.addEventListener('DOMContentLoaded', () => {
    const navItems = document.querySelectorAll('.nav-item');
    const navIndicator = document.querySelector('.nav-indicator');
    const views = document.querySelectorAll('.view');
    const pageTitle = document.getElementById('page-title');
    const pillNavItems = document.querySelectorAll('.nav-pill .nav-item');

    // Initialize indicator position
    function updateIndicator(activeItem) {
        if (!activeItem || !navIndicator) return;
        
        // Check if the item is inside the pill
        if (activeItem.closest('.nav-pill')) {
            // Use offsetLeft and offsetWidth for 100% accurate positioning relative to the parent
            const offset = activeItem.offsetLeft;
            const width = activeItem.offsetWidth;
            
            navIndicator.style.width = `${width}px`;
            navIndicator.style.transform = `translateX(${offset}px)`;
            navIndicator.style.opacity = '1';
        } else {
            // If profile is clicked, we can hide or dim the indicator
            navIndicator.style.opacity = '0.5';
        }
    }

    // Set initial state - wait for fonts to load to prevent wide text icon bug
    document.fonts.ready.then(() => {
        const initialActive = document.querySelector('.nav-item.active');
        updateIndicator(initialActive);
    });

    // Navigation Click Handler
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            // Remove active from all nav items
            navItems.forEach(nav => nav.classList.remove('active'));
            
            // Add active to clicked item
            item.classList.add('active');
            
            // Update Indicator
            updateIndicator(item);

            // Update Page Title
            const newTitle = item.getAttribute('data-title');
            if (newTitle) {
                // Slight animation for title
                pageTitle.style.opacity = '0';
                pageTitle.style.transform = 'translateY(-10px)';
                
                setTimeout(() => {
                    pageTitle.textContent = newTitle;
                    pageTitle.style.opacity = '1';
                    pageTitle.style.transform = 'translateY(0)';
                }, 150);
            }

            // Switch Views
            const targetId = item.getAttribute('data-target');
            views.forEach(view => {
                if (view.id === targetId) {
                    view.classList.add('active');
                } else {
                    view.classList.remove('active');
                }
            });

            // Handle Profile active background
            const profileNav = document.querySelector('.nav-profile');
            if (targetId === 'view-profile') {
                profileNav.classList.add('active-bg');
            } else {
                profileNav.classList.remove('active-bg');
            }
        });
    });

    // Bounce interaction for cards and items
    // (mostly handled by CSS :active, but we can add JS click feedback if needed)
    const bounceItems = document.querySelectorAll('.bounce');
    bounceItems.forEach(el => {
        el.addEventListener('click', () => {
            if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
                window.Telegram.WebApp.HapticFeedback.selectionChanged();
            }
        });
    });

    // --- Telegram Web App Integration ---
    function initTelegram() {
        if (!window.Telegram || !window.Telegram.WebApp) return;
        
        const tg = window.Telegram.WebApp;
        
        // Notify Telegram that the app is ready
        tg.ready();
        
        // Expand the mini app to full screen
        tg.expand();

        // Try to get user data from Telegram environment
        const user = tg.initDataUnsafe?.user;
        
        if (user) {
            // UI Elements
            const profileName = document.getElementById('profile-name');
            const profileUserid = document.getElementById('profile-userid');
            const connectionUsername = document.getElementById('connection-username');
            const profileAvatar = document.getElementById('profile-avatar');

            // 1. Set Full Name in Profile
            const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ');
            if (profileName) {
                profileName.textContent = fullName || user.username || 'Пользователь Telegram';
            }

            // 2. Set Telegram ID
            if (profileUserid) {
                profileUserid.textContent = `ID: ${user.id}`;
            }

            // 3. Set Username in Connection Tab
            if (connectionUsername) {
                const displayName = user.username ? `@${user.username}` : user.first_name;
                connectionUsername.textContent = displayName;
            }

            // 4. Set Avatar Initials
            if (profileAvatar) {
                const initial = (user.first_name || user.username || 'U').charAt(0).toUpperCase();
                // Replace the generic person icon with the user's initial
                profileAvatar.innerHTML = `<span style="font-size: 28px; font-weight: 500;">${initial}</span>`;
                
                // If the user has a premium account, we could potentially style the avatar differently,
                // but photo URL is not directly available via initDataUnsafe.
            }
        }
    }

    initTelegram();
});

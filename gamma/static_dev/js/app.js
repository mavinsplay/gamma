document.addEventListener('DOMContentLoaded', () => {
    const navItems = document.querySelectorAll('.nav-item');
    const navIndicator = document.querySelector('.nav-indicator');
    const SAFE_MOCK_USER_DATA = (typeof MOCK_USER_DATA !== 'undefined') ? MOCK_USER_DATA : null;
    const views = document.querySelectorAll('.view');
    // Слайдер не должен зависеть от числа вьюх: сообщаем CSS реальное
    // количество, иначе новая вьюха (билинг) сдвигает вёрстку на телефоне.
    try {
        document.getElementById('view-wrapper').style.setProperty(
            '--view-count', String(views.length)
        );
    } catch (e) {}
    const pageTitle = document.getElementById('page-title');
    const pillNavItems = document.querySelectorAll('.nav-pill .nav-item');
    window.authenticatedUserId = null;

    // Escape a value for safe insertion into HTML text/attribute content.
    function escapeHtml(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;');
    }

    // Escape a value for safe insertion into a single-quoted JS string that
    // lives inside a double-quoted HTML attribute (e.g. inline onclick).
    function escapeJsAttr(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '\u003c')
            .replace(/>/g, '\u003e')
            .replace(/\\/g, '\\\\')
            .replace(/'/g, "\\'");
    }

    function isDesktop() {
        return window.innerWidth >= 768;
    }

    function showAvatarFallback(img) {
        var el = img.parentElement;
        var initial = el.dataset.initial || 'U';
        el.innerHTML = '<span style="font-size:28px;font-weight:500;">' + initial + '</span>';
    }

    // Telegram WebApp Object
    const tg = window.Telegram?.WebApp;
    if (tg) {
        tg.expand();
        tg.ready();
    }

    // --- Viewport Height Fix for Mobile Browsers ---
    function setVh() {
        let vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    }
    setVh();
    window.addEventListener('resize', setVh);
    window.addEventListener('orientationchange', () => setTimeout(setVh, 100));

    /*
    // --- Security: URL Cleanup ---
    function cleanupUrl() {
        console.log('cleanupUrl: checking params...');
        const url = new URL(window.location.href);
        if (url.searchParams.has('tg_id') || url.searchParams.has('tg_username')) {
            url.searchParams.delete('tg_id');
            url.searchParams.delete('tg_username');
            console.log('cleanupUrl: applying replaceState to', url.toString());
            try {
                window.history.replaceState({}, document.title, url.toString());
                console.log('cleanupUrl: success');
            } catch (e) {
                console.error('cleanupUrl: error', e);
            }
        }
    }
    cleanupUrl();
    */

    // Initialize indicator position
    function updateIndicator(activeItem, noAnimation) {
        if (!activeItem || !navIndicator) return;

        if (noAnimation) {
            navIndicator.style.transition = 'none';
        }

        const pill = activeItem.closest('.nav-pill');
        
        if (pill) {
            // Normal tab: move and size
            const offsetL = activeItem.offsetLeft;
            const offsetT = activeItem.offsetTop;
            const width = activeItem.offsetWidth;
            const height = activeItem.offsetHeight;

            if (isDesktop()) {
                navIndicator.style.transform = `translateY(${offsetT}px)`;
                navIndicator.style.height = `${height}px`;
                navIndicator.style.width = ''; 
            } else {
                navIndicator.style.transform = `translateX(${offsetL}px)`;
                navIndicator.style.width = `${width}px`;
                navIndicator.style.height = '';
            }
            navIndicator.style.opacity = '1';
        } else {
            // Profile tab: just dim it, don't move or resize
            // Special case: if this is the first run (e.g. refresh on profile), 
            // position it over the first nav item so it's aligned.
            if (noAnimation || !navIndicator.style.transform || navIndicator.style.transform === 'none') {
                const firstItem = document.querySelector('.nav-pill .nav-item');
                if (firstItem) {
                    const offsetL = firstItem.offsetLeft;
                    const offsetT = firstItem.offsetTop;
                    const width = firstItem.offsetWidth;
                    const height = firstItem.offsetHeight;
                    
                    if (isDesktop()) {
                        navIndicator.style.transform = `translateY(${offsetT}px)`;
                        navIndicator.style.height = `${height}px`;
                    } else {
                        navIndicator.style.transform = `translateX(${offsetL}px)`;
                        navIndicator.style.width = `${width}px`;
                    }
                }
            }
            navIndicator.style.opacity = '0.5';
        }

        if (noAnimation) {
            navIndicator.offsetHeight;
            navIndicator.style.transition = '';
        }
    }

    function updateViewWrapper(activeItem, noAnimation) {
        if (!activeItem) return;
        const targetId = activeItem.getAttribute('data-target');
        const viewArray = Array.from(views);
        const index = viewArray.findIndex(v => v.id === targetId);
        const wrapper = document.getElementById('view-wrapper');

        if (index !== -1 && wrapper && !isDesktop()) {
            if (noAnimation) {
                wrapper.style.transition = 'none';
            }
            const offset = index * (100 / views.length);
            wrapper.style.transform = `translateX(-${offset}%)`;
            if (noAnimation) {
                wrapper.offsetHeight;
                wrapper.style.transition = '';
            }
        } else if (wrapper) {
            wrapper.style.transform = ''; // Clear transform on desktop
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
        document.body.classList.add('fonts-loaded');
        const initialActive = document.querySelector('.nav-item.active');
        updateIndicator(initialActive, true);
        updateViewWrapper(initialActive, true);
        
        // Secondary check after layout settle
        setTimeout(() => {
            const currentActive = document.querySelector('.nav-item.active');
            updateIndicator(currentActive, true);
            updateViewWrapper(currentActive, true);
        }, 100);
    });

    // Ensure initial tab wrapper is positioned without animation
    setTimeout(() => {
        const initialActive = document.querySelector('.nav-item.active');
        if (initialActive && !sessionStorage.getItem('activeTab')) {
            updateViewWrapper(initialActive, true);
        }
    }, 50);

    // Navigation Click Handler
    function activateTab(item, noAnimation) {
        const targetId = item.getAttribute('data-target');
        const targetTitle = item.getAttribute('data-title');

        // Haptic Feedback for navigation
        if (!noAnimation && window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
        }

        navItems.forEach(nav => nav.classList.remove('active'));
        item.classList.add('active');
        updateIndicator(item);

        if (pageTitle && targetTitle) {
            pageTitle.style.opacity = '0';
            pageTitle.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                pageTitle.textContent = targetTitle;
                pageTitle.style.opacity = '1';
                pageTitle.style.transform = 'translateY(0)';
            }, 150);
        }

        updateViewWrapper(item, noAnimation);

        views.forEach(view => {
            if (view.id === targetId) {
                view.classList.add('active');
            } else {
                view.classList.remove('active');
            }
        });

        // Auto-load connection link when navigating to connection view
        if (targetId === 'view-connection' && !noAnimation && !window._connectFetching) {
            setTimeout(() => {
                if (!window._connectFetching) {
                    const subType = window.selectedSubType || 'main';
                    const cachedLink = subLinkCache[subType];
                    if (!cachedLink && window.authenticatedUserId && window.hasActiveSubscription() && window.handleConnect) {
                        window.handleConnect();
                    }
                }
            }, 350);
        }

        const profileNav = document.querySelector('.nav-profile');
        if (profileNav) {
            if (targetId === 'view-profile') {
                profileNav.classList.add('active-bg');
            } else {
                profileNav.classList.remove('active-bg');
            }
        }

        sessionStorage.setItem('activeTab', targetId);
        sessionStorage.setItem('activeTitle', targetTitle);
    }

    navItems.forEach(item => {
        item.addEventListener('click', () => activateTab(item));
    });

    window.activateTabById = (viewId, title) => {
        const item = Array.from(navItems).find(i => i.getAttribute('data-target') === viewId);
        if (item) {
            activateTab(item);
        } else {
            // Haptic Feedback
            if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
                window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
            }

            navItems.forEach(nav => nav.classList.remove('active'));
            if (pageTitle) pageTitle.textContent = title;

            // Slide animation for sub-views (only for mobile)
            const viewArray = Array.from(views);
            const index = viewArray.findIndex(v => v.id === viewId);
            const wrapper = document.getElementById('view-wrapper');

            if (index !== -1 && wrapper && !isDesktop()) {
                const offset = index * (100 / views.length);
                wrapper.style.transform = `translateX(-${offset}%)`;
            } else if (wrapper) {
                wrapper.style.transform = '';
            }

            views.forEach(v => {
                if (v.id === viewId) v.classList.add('active');
                else v.classList.remove('active');
            });

            if (viewId === 'view-history') window.loadPaymentHistory();
        }
    };

    // Global haptic feedback for all buttons and interactive elements
    document.addEventListener('click', (e) => {
        const target = e.target.closest('.bounce, .action-btn, .v2-buy-btn, .nav-item, .settings-item');
        if (target && window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
        }
    });

    // Deep-link: ?tab=view-xxx overrides saved tab
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    if (tabParam) {
        const viewId = tabParam.startsWith('view-') ? tabParam : 'view-' + tabParam;
        const item = Array.from(navItems).find(
            i => i.getAttribute('data-target') === viewId
        );
        if (item) {
            sessionStorage.setItem('activeTab', viewId);
            activateTab(item, true);
            // Force sync immediately to populate data
            setTimeout(() => {
                if (window.syncNow) window.syncNow();
            }, 100);
        }
    }

    // Restore active tab after page reload
    const savedTab = sessionStorage.getItem('activeTab');
    if (savedTab) {
        const savedItem = Array.from(navItems).find(
            item => item.getAttribute('data-target') === savedTab
        );
        if (savedItem) {
            activateTab(savedItem, true);
        }
    }


    // Drag-to-scroll for card-list on PC
    const slider = document.querySelector('.card-list-vertical'); // Switched to vertical so maybe not needed, but keep for fallback
    if (slider) {
        let isDown = false;
        let startY;
        let scrollTop;

        slider.addEventListener('mousedown', (e) => {
            isDown = true;
            slider.style.cursor = 'grabbing';
            startY = e.pageY - slider.offsetTop;
            scrollTop = slider.scrollTop;
        });

        slider.addEventListener('mouseleave', () => {
            if (!isDown) return;
            isDown = false;
            slider.style.cursor = '';
        });

        slider.addEventListener('mouseup', () => {
            isDown = false;
            slider.style.cursor = '';
        });

        slider.addEventListener('mousemove', (e) => {
            if (!isDown) return;
            e.preventDefault();
            const y = e.pageY - slider.offsetTop;
            const walk = (y - startY) * 2;
            slider.scrollTop = scrollTop - walk;
        });
    }

    window.handleLogout = async () => {
        try {
            const response = await fetch('/user/logout/');
            const data = await response.json();
            if (data.success) {
                window.location.reload();
            }
        } catch (error) {
            console.error('Logout error:', error);
            alert('Ошибка при выходе');
        }
    };

    function checkAdmin() {
        const isAdmin = Boolean(window.authenticatedUserId && typeof ADMIN_ID !== 'undefined' && String(window.authenticatedUserId) === String(ADMIN_ID));
        const adminLink = document.getElementById('admin-panel-link');
        if (adminLink) adminLink.style.display = isAdmin ? 'flex' : 'none';
        const billingLink = document.getElementById('billing-panel-link');
        if (billingLink) billingLink.style.display = isAdmin ? 'flex' : 'none';
    }

    async function initTelegram() {
        let user = null;
        const authOverlay = document.getElementById('auth-overlay');

        const tg = window.Telegram?.WebApp;
        const isTelegramHash = window.location.hash.includes('tgWebAppData');
        window._isMiniApp = (tg && tg.initData) || isTelegramHash;

        // 1. Check if inside Telegram Mini App (via API or URL hash)
        if ((tg && tg.initData) || isTelegramHash) {
            console.log('Telegram Mini-App environment detected.');
            if (tg) {
                tg.ready();
                tg.expand();
                if (tg.initDataUnsafe?.user) {
                    user = tg.initDataUnsafe.user;
                    window.authenticatedUserId = user.id;
                    checkAdmin();
                }
            }
            // Hide logout button in Telegram
            const logoutElements = ['.logout-btn', '#logout-btn', '#logout-item'];
            logoutElements.forEach(selector => {
                const el = document.querySelector(selector);
                if (el) el.style.display = 'none';
            });

            // ВАЖНО: Если мы в телеграме, мы НИКОГДА не делаем редирект отсюда.
            // Синхронизация данных (startDataSync) всё поправит.
        }
        // 2. Check for Mock Data (Debug only)
        else if (IS_DEBUG && SAFE_MOCK_USER_DATA) {
            console.log('Using mock user data for development');
            user = SAFE_MOCK_USER_DATA;
            window.authenticatedUserId = user.id;
            checkAdmin();
        }
        // 3. Check Backend Session (Browser mode)
        else {
            try {
                const response = await fetch('/user/status/');
                const data = await response.json();
                if (data.authenticated) {
                    user = data.user;
                    window.authenticatedUserId = user.id;
                    checkAdmin();
                } else {
                    // Редирект ТОЛЬКО если мы уверены, что это не Телеграм
                    console.log('Not in Telegram and not authenticated. Redirecting...');
                    window.location.href = '/user/login-page/';
                    return;
                }
            } catch (error) {
                console.error('Failed to check auth status:', error);
            }
        }

        // Final Auth Check
        if (user) {
            // Authorized
        } else {
            // Should not happen if backend redirect is working
            return;
        }

        if (user) {
            // Update UI with user data
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
                if (user.id) {
                    profileAvatar.dataset.initial = initial;
                    var avatarUrl;
                    if (IS_DEBUG && user.photo_url) {
                        avatarUrl = user.photo_url;
                    } else {
                        avatarUrl = '/user/avatar/';
                    }
                    profileAvatar.innerHTML = '<img src="' + avatarUrl + '" style="width:100%;height:100%;border-radius:50%;object-fit:cover;border:2px solid var(--md-sys-color-primary-container);" onerror="showAvatarFallback(this)">';
                } else {
                    profileAvatar.innerHTML = '<span style="font-size:28px;font-weight:500;">' + initial + '</span>';
                }
            }

            // Sync logic if needed (Legacy tg_id param logic can be removed or kept as fallback)
            /*
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('tg_id') != user.id) {
                urlParams.set('tg_id', user.id);
                if (user.username) urlParams.set('tg_username', user.username);
                window.location.search = urlParams.toString();
                return;
            }
            */
        }

        // Привязка реферала из ?ref= (если пришли по реферальной ссылке)
        bindReferralFromUrl();
    }

    initTelegram();

    // Modal Handling
    const modalOverlay = document.getElementById('modal-overlay');
    const modalTitle = document.getElementById('modal-title');
    const modalMessage = document.getElementById('modal-message');
    const modalIcon = document.getElementById('modal-icon-text');
    const modalClose = document.getElementById('modal-close');
    const modalAction = document.getElementById('modal-action');
    const modalInputContainer = document.getElementById('modal-input-container');
    const modalAmountInput = document.getElementById('modal-amount-input');

    let modalKeepOpen = false;
    let showModalCount = 0;

    function showModal({ title, message, icon = 'info', actionText = 'Пополнить', onAction = null, showInput = false, inputValue = '', inputPlaceholder = 'Введите данные...', inputType = 'text', customHtml = '', closeBtnText = 'Закрыть' }) {
        showModalCount++;

        // Если модалка уже открыта — оверлей не трогаем (иначе будет
        // резкое мигание opacity 1 -> 0 -> 1). Анимируем только бокс
        // лёгким pop, как при обычном открытии.
        const wasOpen = modalOverlay.classList.contains('active');
        const modalBox = document.getElementById('modal-content');

        modalTitle.textContent = title;
        modalMessage.textContent = message;
        modalIcon.textContent = icon;
        modalAction.textContent = actionText;
        modalClose.textContent = closeBtnText;

        if (showInput) {
            modalInputContainer.style.display = 'block';
            modalAmountInput.value = inputValue;
            modalAmountInput.placeholder = inputPlaceholder;
            modalAmountInput.type = inputType;
            modalAmountInput.focus();
        } else {
            modalInputContainer.style.display = 'none';
        }

        let customContainer = document.getElementById('modal-custom-content');
        if (!customContainer) {
            customContainer = document.createElement('div');
            customContainer.id = 'modal-custom-content';
            customContainer.style.width = '100%';
            customContainer.style.marginTop = '15px';
            modalInputContainer.parentNode.insertBefore(customContainer, modalInputContainer);
        }

        if (customHtml) {
            customContainer.style.display = 'block';
            customContainer.innerHTML = customHtml;
        } else {
            customContainer.style.display = 'none';
            customContainer.innerHTML = '';
        }

        if (onAction) {
            modalAction.style.display = 'block';
            modalAction.classList.remove('copied');
            modalAction.onclick = () => {
                modalKeepOpen = false;
                const prevCount = showModalCount;
                const result = onAction();
                // Only hide if no other modal was opened during onAction,
                // the action didn't request to stay open (e.g. debug mode)
                // and didn't return false (inline feedback, modal stays).
                if (
                    !modalKeepOpen
                    && showModalCount === prevCount
                    && result !== false
                ) {
                    hideModal();
                }
            };
        } else {
            modalAction.style.display = 'none';
        }

        if (!wasOpen) {
            modalOverlay.classList.add('active');
        } else if (modalBox && modalBox.animate) {
            modalBox.animate(
                [{ transform: 'scale(0.96)' }, { transform: 'scale(1)' }],
                { duration: 180, easing: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)' }
            );
        } else {
            modalOverlay.classList.add('active');
        }
    }

    function hideModal() {
        modalOverlay.classList.remove('active');
        modalClose.textContent = 'Закрыть';
        // Clean up extra buttons if any
        document.querySelectorAll('.test-topup-extra').forEach(el => el.remove());
    }

    modalClose.onclick = hideModal;
    modalOverlay.onclick = (e) => {
        if (e.target === modalOverlay) hideModal();
    };

    function showPaymentMethodPicker(amount) {
        let selectedMethod = 'yoomoney';
        const bonuses = window._topupBonuses || {card: 0, sbp: 4, crypto: 4};
        const methodBonus = (m) => Number((bonuses[m === 'yoomoney' ? 'card' : m]) || 0);
        const bonusPill = (m) => {
            const pct = methodBonus(m);
            if (!(pct > 0)) return '';
            return `<br><span style="display: inline-block; margin-top: 4px; font-size: 11px; font-weight: 700; color: #4CAF50; background: rgba(76, 175, 80, 0.12); border-radius: 8px; padding: 2px 8px;">+${pct}% к балансу</span>`;
        };
        const pickerMessage = (m) => {
            const pct = methodBonus(m);
            if (pct > 0) {
                const credit = Math.floor(Number(amount) * (1 + pct / 100) * 100) / 100;
                return `Сумма: ${amount} ₽. К зачислению: ${credit} ₽ (бонус +${pct}%). Выберите метод оплаты:`;
            }
            return `Сумма: ${amount} ₽. Выберите метод оплаты:`;
        };
        const html = `
            <div class="payment-methods-list">
                <div class="payment-method-item selected bounce" data-method="yoomoney">
                    <div class="payment-method-icon-wrapper">
                        <svg class="pm-brand-icon yoomoney-logo" viewBox="0 0 1000 700" aria-label="ЮMoney" xmlns="http://www.w3.org/2000/svg">
                            <path fill="#8B3FFD" fill-rule="evenodd" clip-rule="evenodd" d="M288.3,349c0.5-192.3,158-349,355.9-349c195.9,0,358.1,157.3,355.8,350c0,192.7-159.9,350-355.8,350C448.4,700,288.7,545.4,288.3,349.9V610.4H162.2L0,101.9h288.3V349zM511.2,350c0,70.9,60.8,130.7,132.9,130.7c74.3,0,132.9-59.8,132.9-130.7c0-70.9-60.8-130.7-132.9-130.7C572.1,219.3,511.2,279.1,511.2,350z"/>
                        </svg>
                    </div>
                    <div class="payment-method-info">
                        <div class="payment-method-title">По карте</div>
                        <div class="payment-method-desc">Российские карты (ЮМани)</div>
                    </div>
                    <div class="payment-method-check">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M5 13l4 4L19 7"/>
                        </svg>
                    </div>
                </div>
                <div class="payment-method-item bounce" data-method="sbp">
                    <div class="payment-method-icon-wrapper sbp-logo-wrapper">
                        <svg class="sbp-logo" viewBox="0 0 345.5 398.9" aria-label="СБП" xmlns="http://www.w3.org/2000/svg">
                            <path fill="#8F4794" d="M100.3,199.4l-52,30L0,313.1l196.9-113.7L100.3,199.4z"/>
                            <path fill="#E40646" d="M248.9,113.7l-52,30l-48.3,83.7l196.9-113.7L248.9,113.7z"/>
                            <polygon fill="#F9B429" points="196.9,83.7 148.6,0 148.6,171.5 148.6,227.4 148.6,398.9 196.9,315.2"/>
                            <polygon fill="#EF8019" points="148.6,0 196.9,83.7 248.9,113.7 345.5,113.7"/>
                            <polygon fill="#78B72A" points="148.6,171.5 148.6,398.9 196.9,315.2 196.9,255.2"/>
                            <path fill="#00853F" d="M248.9,285.2l-52,30l-48.3,83.7l196.9-113.7L248.9,285.2z"/>
                            <polygon fill="#5B57A2" points="0,85.8 0,313.1 48.3,229.5 48.3,169.4"/>
                            <polygon fill="#0698D6" points="148.6,171.5 148.7,171.6 0,85.8 48.3,169.4 248.9,285.2 345.5,285.2"/>
                        </svg>
                    </div>
                    <div class="payment-method-info">
                        <div class="payment-method-title">СБП</div>
                        <div class="payment-method-desc">Система быстрых платежей (Platega)${bonusPill('sbp')}</div>
                    </div>
                    <div class="payment-method-check">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M5 13l4 4L19 7"/>
                        </svg>
                    </div>
                </div>
                <div class="payment-method-item bounce" data-method="crypto">
                    <div class="payment-method-icon-wrapper crypto-badge">
                        <svg class="pm-brand-icon" viewBox="0 0 24 24" aria-label="Криптовалюта">
                            <circle cx="12" cy="12" r="12" fill="#F7931A"/>
                            <path d="M15.4 10.6c.2-1.3-.8-2-2.1-2.4l.4-1.7-1.1-.3-.4 1.6c-.3-.1-.6-.1-.9-.2l.4-1.6-1.1-.3-.4 1.7c-.2-.1-.5-.2-.7-.3l-1.5-.4-.3 1.1s.8.2.8.2c.4.1.5.4.5.6l-1.2 4.9c-.1.2-.3.5-.7.4 0 0-.8-.2-.8-.2l-.5 1.2 1.5.4c.3.1.5.2.8.3l-.4 1.8 1.1.3.4-1.7c.3.1.6.2.9.3l-.4 1.7 1.1.3.4-1.8c1.8.3 3.2.2 3.8-1.5.5-1.4-.1-2.3-1-2.8.7-.2 1.2-.6 1.3-1.4zm-2.4 3c-.3 1.2-2.4.6-3.1.4l.6-2.4c.7.2 2.9.5 2.5 2zm.3-3.1c-.3 1.1-2.1.5-2.7.4l.5-2.1c.6.1 2.5.4 2.2 1.7z" fill="#FFFFFF"/>
                        </svg>
                    </div>
                    <div class="payment-method-info">
                        <div class="payment-method-title">Криптовалюта</div>
                        <div class="payment-method-desc">USDT, TON, TRX и др. (Platega)${bonusPill('crypto')}</div>
                    </div>
                    <div class="payment-method-check">✓</div>
                </div>
            </div>
        `;
        showModal({
            title: 'Способ оплаты',
            message: pickerMessage(selectedMethod),
            icon: 'account_balance_wallet',
            actionText: 'Оплатить',
            showInput: false,
            customHtml: html,
            onAction: () => {
                performTopup(amount, selectedMethod);
            }
        });
        setTimeout(() => {
            const items = document.querySelectorAll('.payment-method-item');
            items.forEach(item => {
                item.onclick = () => {
                    items.forEach(i => i.classList.remove('selected'));
                    item.classList.add('selected');
                    selectedMethod = item.getAttribute('data-method');
                    const msgEl = document.getElementById('modal-message');
                    if (msgEl) msgEl.textContent = pickerMessage(selectedMethod);
                };
            });
        }, 50);
    }

    window.handleTopup = (initialAmount = '', pendingPurchase = null) => {
        // Покупка, которую пользователь хотел совершить, но не хватило
        // средств. После успешной оплаты она выполнится автоматически.
        // Ручное пополнение (без pendingPurchase) сбрасывает отложенную.
        pendingPurchaseAfterTopup = pendingPurchase || null;
        let message = initialAmount
            ? `На вашем счёте недостаточно ${initialAmount} ₽. Введите сумму для пополнения:`
            : 'Введите сумму, на которую вы хотите пополнить счёт:';
        if (pendingPurchaseAfterTopup) {
            message += ' После пополнения покупка завершится автоматически.';
        }
        showModal({
            title: 'Пополнение баланса',
            message: message,
            icon: 'payments',
            actionText: 'Продолжить',
            showInput: true,
            inputValue: initialAmount,
            inputPlaceholder: 'Сумма в рублях',
            inputType: 'number',
            onAction: () => {
                const amount = parseFloat(modalAmountInput.value);
                if (isNaN(amount) || amount <= 0) {
                    alert('Пожалуйста, введите корректную сумму.');
                    return;
                }
                showPaymentMethodPicker(amount);
            }
        });
    };

    // Отложенная покупка после пополнения баланса.
    // Формат: {kind: 'buy'|'extend'|'slot'|'wl', ...params}.
    let pendingPurchaseAfterTopup = null;

    async function runPendingPurchase() {
        const pending = pendingPurchaseAfterTopup;
        pendingPurchaseAfterTopup = null;
        if (!pending) return false;
        try {
            if (pending.kind === 'buy') {
                await performBuy(
                    pending.tariffId,
                    pending.price,
                    pending.userId,
                    pending.username,
                    pending.replace
                );
            } else if (pending.kind === 'extend') {
                await performExtend(pending.months, pending.subType);
            } else if (pending.kind === 'slot') {
                await performBuySlot();
            } else if (pending.kind === 'wl') {
                await performWhitelistTopup();
            }
        } catch (e) {
            // Ошибки уже показаны модалками внутри perform-функций
        }
        return true;
    }

    // Общий обработчик успешной оплаты: обновить баланс и либо
    // автоматически завершить отложенную покупку, либо показать
    // стандартное окно «Баланс пополнен».
    async function onTopupPaid(newBalance) {
        const balanceAmount = document.getElementById('profile-balance');
        if (balanceAmount && newBalance !== undefined) {
            balanceAmount.textContent = `${newBalance.toFixed(0)} ₽`;
        }
        if (pendingPurchaseAfterTopup) {
            if (window.syncNow) window.syncNow();
            await runPendingPurchase();
            return;
        }
        showModal({
            title: 'Готово!',
            message: `Баланс пополнен.`,
            icon: 'check_circle',
            actionText: 'Отлично',
            onAction: () => {
                modalKeepOpen = false;
                hideModal();
                if (window.syncNow) window.syncNow();
            }
        });
        if (window.syncNow) window.syncNow();
    }

    const PENDING_PAYMENT_KEY = 'gamma_pending_payment';
    let paymentTimerInterval = null;
    let paymentTimerSeconds = 0;

    function startPaymentTimer(orderId, amount, paymentUrl, expiresAt, paymentProvider) {
        if (!expiresAt) {
            expiresAt = Date.now() + 10 * 60 * 1000;
        }
        try {
            localStorage.setItem(PENDING_PAYMENT_KEY, JSON.stringify({
                orderId: orderId,
                amount: amount,
                paymentUrl: paymentUrl,
                paymentProvider: paymentProvider || 'yoomoney',
                expiresAt: expiresAt
            }));
        } catch (e) {}
        paymentTimerSeconds = Math.ceil((expiresAt - Date.now()) / 1000);
        if (paymentTimerSeconds < 0) paymentTimerSeconds = 0;
        showPaymentBanner(amount, paymentTimerSeconds);
        showRetryButton(paymentUrl);
        pollPaymentStatus(orderId);
        clearInterval(paymentTimerInterval);
        paymentTimerInterval = setInterval(tickPaymentTimer, 1000);
    }

    function showRetryButton(paymentUrl) {
        const btn = document.getElementById('payment-retry-btn');
        if (!btn) return;
        btn.style.display = 'flex';
        btn.onclick = function(e) {
            e.stopPropagation();
            const tg = window.Telegram?.WebApp;
            if (tg?.openLink) {
                tg.openLink(paymentUrl);
            } else {
                window.open(paymentUrl, '_blank');
            }
        };
    }

    let paymentPollInterval = null;

    async function pollPaymentStatus(orderId) {
        clearInterval(paymentPollInterval);
        paymentPollInterval = setInterval(async () => {
            try {
                const tg = window.Telegram?.WebApp;
                const resp = await fetch(`/shop/check-payment-api/${orderId}/`);
                const data = await resp.json();
                if (data.status === 'paid') {
                    clearInterval(paymentPollInterval);
                    paymentPollInterval = null;
                    clearPaymentState();
                    await onTopupPaid(data.new_balance);
                } else if (data.status === 'failed') {
                    clearInterval(paymentPollInterval);
                    paymentPollInterval = null;
                    pendingPurchaseAfterTopup = null;
                    clearPaymentState();
                    showModal({
                        title: 'Платёж не прошёл',
                        message: 'Платёж был отклонён или время истекло.',
                        icon: 'error',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                }
            } catch (e) {
                // silent — retry on next interval
            }
        }, 5000);
    }

    function showPaymentBanner(amount, seconds) {
        const banner = document.getElementById('pending-payment-banner');
        if (!banner) return;
        const currentOrderId = lastPendingOrderId || getStoredOrderId();
        const isDismissed = currentOrderId && sessionStorage.getItem('dismissed_payment_banner_' + currentOrderId) === 'true';
        if (isDismissed) {
            banner.style.display = 'none';
            return;
        }
        const title = banner.querySelector('.pending-payment-title');
        const subtitle = banner.querySelector('.pending-payment-subtitle');
        if (title) title.textContent = `Платёж ${amount} ₽ обрабатывается`;
        const m = String(Math.floor((seconds || 600) / 60)).padStart(2, '0');
        const s = String((seconds || 600) % 60).padStart(2, '0');
        if (subtitle) subtitle.innerHTML = `Осталось: <span id="payment-timer" class="payment-timer">${m}:${s}</span>`;
        banner.style.display = 'block';
    }

    function tickPaymentTimer() {
        paymentTimerSeconds--;
        const timerEl = document.getElementById('payment-timer');
        if (timerEl) {
            const m = String(Math.floor(Math.max(paymentTimerSeconds, 0) / 60)).padStart(2, '0');
            const s = String(Math.max(paymentTimerSeconds, 0) % 60).padStart(2, '0');
            timerEl.textContent = `${m}:${s}`;
        }
        if (paymentTimerSeconds <= 0) {
            clearInterval(paymentTimerInterval);
            paymentTimerInterval = null;
            // Don't show modal — wait for sync to detect expiry/success
        }
    }

    function clearPaymentState() {
        modalKeepOpen = false;
        try {
            localStorage.removeItem(PENDING_PAYMENT_KEY);
        } catch (e) {}
        clearInterval(paymentTimerInterval);
        paymentTimerInterval = null;
        clearInterval(paymentPollInterval);
        paymentPollInterval = null;
        const banner = document.getElementById('pending-payment-banner');
        if (!banner) return;
        banner.style.display = 'none';
        const title = banner.querySelector('.pending-payment-title');
        const subtitle = banner.querySelector('.pending-payment-subtitle');
        if (title) title.textContent = 'Платёж обрабатывается';
        if (subtitle) subtitle.innerHTML = 'Не закрывайте приложение';
        const retryBtn = document.getElementById('payment-retry-btn');
        if (retryBtn) retryBtn.style.display = 'none';
    }

    function checkPendingPaymentOnLoad() {
        try {
            const stored = localStorage.getItem(PENDING_PAYMENT_KEY);
            if (!stored) return;
            const data = JSON.parse(stored);
            const remaining = data.expiresAt - Date.now();
            if (remaining <= 0) {
                localStorage.removeItem(PENDING_PAYMENT_KEY);
                return;
            }
            paymentTimerSeconds = Math.ceil(remaining / 1000);
            showPaymentBanner(data.amount, paymentTimerSeconds);
            if (data.paymentUrl) {
                showRetryButton(data.paymentUrl);
            }
            pollPaymentStatus(data.orderId);
            clearInterval(paymentTimerInterval);
            paymentTimerInterval = setInterval(tickPaymentTimer, 1000);
        } catch (e) {
            try { localStorage.removeItem(PENDING_PAYMENT_KEY); } catch (e) {}
        }
    }

    async function performTopup(amount, paymentMethod = 'yoomoney') {
        // Keep the picker open synchronously (before any await) so the modal
        // wrapper doesn't auto-close it while we await the fetch in dev mode.
        if (typeof IS_DEBUG !== 'undefined' && IS_DEBUG) {
            modalKeepOpen = true;
        }
        const tg = window.Telegram?.WebApp;
        const userId = window.authenticatedUserId;

        if (!userId || userId === 'undefined') {
            showModal({
                title: 'Ошибка',
                message: 'Ваш профиль еще не загружен. Пожалуйста, подождите секунду и попробуйте снова.',
                icon: 'hourglass_empty',
                actionText: 'Ок',
                onAction: hideModal
            });
            return;
        }

        try {
            const formData = new FormData();
            formData.append('amount', amount);
            formData.append('payment_provider', paymentMethod);
            formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

            if (tg?.initData) {
                formData.append('init_data', tg.initData);
            }

            const response = await fetch('/shop/topup-api/', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                if (data.payment_url) {
                    var expiresAt = data.expires_at
                        ? new Date(data.expires_at).getTime()
                        : (Date.now() + 10 * 60 * 1000);
                    startPaymentTimer(data.order_id, amount, data.payment_url, expiresAt, paymentMethod);
                    if (typeof IS_DEBUG !== 'undefined' && IS_DEBUG) {
                        // Keep the payment method picker open in dev mode
                        // and show a live countdown inside it instead of
                        // closing it / redirecting.
                        modalTitle.textContent = 'Оплата (отладка)';
                        modalIcon.textContent = 'science';
                        modalAction.style.display = 'none';
                        modalInputContainer.style.display = 'none';
                        let customContainer = document.getElementById('modal-custom-content');
                        if (!customContainer) {
                            customContainer = document.createElement('div');
                            customContainer.id = 'modal-custom-content';
                            customContainer.style.width = '100%';
                            customContainer.style.marginTop = '15px';
                            modalInputContainer.parentNode.insertBefore(customContainer, modalInputContainer);
                        }
                        customContainer.style.display = 'block';
                        customContainer.innerHTML =
                            '<div style="text-align:center;color:#CAC4D0;font-size:14px;line-height:1.5;">'
                            + `Платёж на <strong>${amount} ₽</strong> будет эмулирован.<br>`
                            + 'Не закрывайте это окно — статус обновится автоматически.</div>'
                            + '<div id="debug-pay-timer" style="text-align:center;font-size:32px;font-weight:700;color:#D0BCFF;margin-top:12px;">0:15</div>';
                        let debugLeft = 15;
                        const debugTimerEl = document.getElementById('debug-pay-timer');
                        clearInterval(window.__debugPayTimer);
                        window.__debugPayTimer = setInterval(() => {
                            debugLeft--;
                            if (debugTimerEl) {
                                const m = String(Math.floor(Math.max(debugLeft, 0) / 60)).padStart(2, '0');
                                const s = String(Math.max(debugLeft, 0) % 60).padStart(2, '0');
                                debugTimerEl.textContent = `${m}:${s}`;
                            }
                            if (debugLeft <= 0) clearInterval(window.__debugPayTimer);
                        }, 1000);
                    } else {
                        if (tg?.openLink) {
                            tg.openLink(data.payment_url);
                        } else {
                            window.location.href = data.payment_url;
                        }
                    }
                    if (window.syncNow) window.syncNow();
                    return;
                }

                const balanceAmount = document.getElementById('profile-balance');
                if (balanceAmount) {
                    balanceAmount.textContent = `${data.new_balance.toFixed(0)} ₽`;
                }

                document.querySelectorAll('.test-topup-extra').forEach(el => el.remove());

                showModal({
                    title: 'Готово!',
                    message: `Ваш баланс успешно пополнен на ${amount} ₽.`,
                    icon: 'check_circle',
                    actionText: 'Отлично',
                    onAction: () => {
                        hideModal();
                        if (window.syncNow) window.syncNow();
                    }
                });
                if (window.syncNow) window.syncNow();
            } else if (response.status === 409) {
                if (data.existing_order_id && data.payment_url) {
                    startPaymentTimer(
                        data.existing_order_id,
                        amount,
                        data.payment_url,
                        null,
                        data.payment_provider
                    );
                }
                if (window.syncNow) window.syncNow();
                showModal({
                    title: 'Платёж уже выполняется',
                    message: data.error || 'У вас уже есть ожидающий платёж. Дождитесь его завершения.',
                    icon: 'hourglass_top',
                    actionText: 'Ок',
                    onAction: hideModal
                });
            } else {
                showModal({
                    title: 'Ошибка',
                    message: data.error || 'Не удалось пополнить баланс.',
                    icon: 'error',
                    actionText: 'Ок',
                    onAction: hideModal
                });
            }
        } catch (error) {
            showModal({
                title: 'Ошибка сети',
                message: 'Проверьте интернет-соединение.',
                icon: 'cloud_off',
                actionText: 'Ок',
                onAction: hideModal
            });
        }
    }

    // Promo Code Handler
    window.handlePromoCode = () => {
        showModal({
            title: 'Промокод',
            message: 'Введите ваш промокод:',
            icon: 'redeem',
            actionText: 'Активировать',
            showInput: true,
            inputValue: '',
            inputPlaceholder: 'Введите промокод',
            inputType: 'text',
            onAction: async () => {
                const code = modalAmountInput.value.trim();
                if (!code) {
                    alert('Пожалуйста, введите промокод.');
                    return;
                }

                showLoading('Активация промокода...');

                const tg = window.Telegram?.WebApp;
                const userId = window.authenticatedUserId;

                try {
                    const formData = new FormData();
                    formData.append('code', code);
                    formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

                    if (tg?.initData) {
                        formData.append('init_data', tg.initData);
                    }

                    const response = await fetch('/shop/promo-api/', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok && data.success) {
                        const balanceAmount = document.getElementById('profile-balance');
                        if (balanceAmount) {
                            balanceAmount.textContent = `${data.new_balance.toFixed(0)} ₽`;
                        }

                        const rewardText = data.reward_type === 'BALANCE'
                            ? `Ваш баланс пополнен на ${data.reward_value.toFixed(0)} ₽`
                            : `Подписка продлена на ${data.reward_value.toFixed(0)} дней`;

                        showSuccessAnim(() => {
                            showModal({
                                title: 'Промокод активирован!',
                                message: rewardText,
                                icon: 'check_circle',
                                actionText: 'Отлично',
                                onAction: () => {
                                    hideModal();
                                    if (window.syncNow) window.syncNow();
                                }
                            });
                        });
                        if (window.syncNow) window.syncNow();
                    } else {
                        hideLoading();
                        showModal({
                            title: 'Ошибка',
                            message: data.error || 'Не удалось активировать промокод.',
                            icon: 'error',
                            actionText: 'Ок',
                            onAction: hideModal
                        });
                    }
                } catch (error) {
                    hideLoading();
                    showModal({
                        title: 'Ошибка сети',
                        message: 'Проверьте интернет-соединение.',
                        icon: 'cloud_off',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                }
            }
        });
    };

    // Loading Animation
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');
    const spinner = loadingOverlay?.querySelector('.spinner');
    const successIcon = loadingOverlay?.querySelector('.success-icon-wrapper');

    function showLoading(text = 'Обработка...') {
        loadingText.textContent = text;
        loadingOverlay.classList.remove('success');
        loadingOverlay.classList.add('active');
    }

    function showSuccessAnim(callback) {
        loadingOverlay.classList.add('success');
        if (successIcon) successIcon.style.display = 'flex';
        if (spinner) spinner.style.display = 'none';

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
        }
        setTimeout(() => {
            if (successIcon) successIcon.style.display = 'none';
            if (spinner) spinner.style.display = 'block';
            loadingOverlay.classList.remove('active');
            if (callback) callback();
        }, 500); // Wait for animation to complete
    }

    function hideLoading() {
        loadingOverlay.classList.remove('active');
        loadingOverlay.classList.remove('success');
    }

    async function performBuy(tariffId, price, userId, username, replace = false) {
        showLoading(replace ? 'Замена подписки...' : 'Оформление подписки...');
        console.log('performBuy: starting for tariff', tariffId);
        const tg = window.Telegram?.WebApp;

        try {
            const formData = new FormData();
            formData.append('tariff_id', tariffId);
            formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

            // Pass initData for secure verification
            if (tg?.initData) {
                formData.append('init_data', tg.initData);
            }

            if (replace) formData.append('replace', 'true');

            const response = await fetch('/shop/buy-api/', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                const balanceAmount = document.getElementById('profile-balance');
                if (balanceAmount) {
                    balanceAmount.textContent = `${data.new_balance.toFixed(0)} ₽`;
                }
                window.OPTIMISTIC_HAS_SUB = true;
                window.HAS_ACTIVE_SUB = true;

                // Instant tariff info update
                window.REMAINING_DAYS = data.remaining_days || 0;
                window.CURRENT_TARIFF_NAME = data.tariff_name || '';
                window.CURRENT_TARIFF_PRICE = data.tariff_price || 0;
                window.CURRENT_TARIFF_DAYS = data.tariff_days || 0;
                window.CURRENT_TARIFF_ID = data.sub?.uuid ? 0 : window.CURRENT_TARIFF_ID;
                window.TARIFF_CHANGE_LOCKED = !!data.tariff_change_locked;

                // Update subscription card instantly
                const statusText = document.getElementById('sub-status-text');
                if (statusText) {
                    if (data.remaining_days > 0) {
                        const dateStr = data.expire_at ? new Date(data.expire_at).toLocaleDateString('ru-RU', {day:'numeric', month:'short'}) : '';
                        statusText.innerHTML = `До <span>${dateStr}</span> &bull; ${data.remaining_days} дн.`;
                    } else {
                        statusText.textContent = 'Активна';
                    }
                }
                const subStatus = document.querySelector('.sub-status-minimal');
                if (subStatus) {
                    subStatus.className = 'sub-status-minimal ' +
                        (data.remaining_days > 3 ? 'status-active' : data.remaining_days > 0 ? 'status-expiring' : 'status-active');
                }
                const subTitle = document.getElementById('sub-title-display');
                if (subTitle) subTitle.textContent = data.tariff_name || 'Premium';

                // Update tariff card buttons instantly
                document.querySelectorAll('.tariff-card-v2').forEach(card => {
                    const title = card.querySelector('h3');
                    const btn = card.querySelector('.v2-buy-btn');
                    if (btn && title) {
                        if (title.textContent === data.tariff_name) {
                            btn.textContent = 'Уже активен';
                            btn.disabled = true;
                            btn.style.opacity = '0.5';
                            btn.title = '';
                        } else if (window.TARIFF_CHANGE_LOCKED) {
                            btn.textContent = 'Недоступно';
                            btn.disabled = true;
                            btn.style.opacity = '0.5';
                            btn.title = 'Ваш текущий тариф нельзя сменить';
                        } else {
                            btn.textContent = 'Заменить';
                            btn.disabled = false;
                            btn.style.opacity = '1';
                            btn.title = '';
                        }
                    }
                });

                // Dynamically add whitelist card if needed
                if (data.has_whitelist) {
                    window.HAS_WHITELIST_SUB = true;
                    const subSlider = document.getElementById('sub-slider');
                    const existingWl = document.querySelector('.wl-slide');
                    if (subSlider && !existingWl) {
                        const wlSlide = document.createElement('div');
                        wlSlide.className = 'sub-slide bounce wl-slide';
                        wlSlide.innerHTML = `
                            <div class="sub-header">
                                <div class="sub-icon wl-icon">
                                    <span class="material-symbols-rounded">shield_locked</span>
                                </div>
                                <div class="sub-info">
                                    <span class="sub-label">Дополнительная подписка</span>
                                    <h3 class="sub-title">Расширенный доступ</h3>
                                </div>
                            </div>
                            <div class="sub-status-minimal status-active">
                                <div class="status-dot"></div>
                                <span id="wl-status-text">Активна</span>
                            </div>
                            <div class="wl-traffic-bar">
                                <div class="wl-traffic-info">
                                    <span style="opacity:0.8; font-size:12px;">Трафик:</span>
                                    <span id="wl-traffic-text" style="font-size:12px; font-weight:500;">Загрузка...</span>
                                </div>
                                <div class="wl-progress-bg">
                                    <div class="wl-progress-fill" id="wl-traffic-progress" style="width: 0%"></div>
                                </div>
                            </div>
                            <div class="sub-footer">
                                <div class="sub-actions">
                                    <button class="action-btn bounce extend-btn" style="background: rgba(76, 175, 80, 0.15); color: #4CAF50;" onclick="handleTopupWhitelistTraffic()">
                                        <span class="material-symbols-rounded">add_circle</span>+5 ГБ за 150 ₽
                                    </button>
                                    <button class="action-btn bounce connect-btn" onclick="connectAndSwitch('whitelist')">
                                        <span class="material-symbols-rounded">vpn_key</span>Подключить
                                    </button>
                                </div>
                            </div>`;
                        subSlider.appendChild(wlSlide);
                        // Show slider dots
                        const dots = document.getElementById('sub-slider-dots');
                        if (dots) dots.style.display = '';
                    }
                } else if (!data.has_whitelist) {
                    window.HAS_WHITELIST_SUB = false;
                    const existingWl = document.querySelector('.wl-slide');
                    if (existingWl) existingWl.remove();
                    const dots = document.getElementById('sub-slider-dots');
                    if (dots) dots.style.display = 'none';
                    const existingSwitcher = document.getElementById('sub-type-switcher');
                    if (existingSwitcher) existingSwitcher.remove();
                    const result = document.getElementById('connection-result');
                    if (result) {
                        result.classList.remove('animate-in');
                        result.classList.add('hiding');
                    }
                }

                // Update connection view switcher
                const connInfo = document.querySelector('#view-connection .subscription-info');
                if (connInfo && data.has_whitelist) {
                    const existingSwitcher = document.getElementById('sub-type-switcher');
                    if (!existingSwitcher) {
                        const anchor = document.getElementById('conn-loading-placeholder')
                            || document.getElementById('connection-result');
                        if (anchor) {
                            const switcher = document.createElement('div');
                            switcher.id = 'sub-type-switcher';
                            switcher.className = 'sub-type-switcher';
                            switcher.innerHTML = `
                                <div class="sub-type-indicator"></div>
                                <button id="sub-type-main" class="sub-type-btn active" onclick="switchSubType('main')">
                                    <span class="material-symbols-rounded" style="font-size: 16px; vertical-align: middle; margin-right: 4px;">verified_user</span>Основная
                                </button>
                                <button id="sub-type-whitelist" class="sub-type-btn" onclick="switchSubType('whitelist')">
                                    <span class="material-symbols-rounded" style="font-size: 16px; vertical-align: middle; margin-right: 4px;">shield_locked</span>Дополнительная
                                </button>`;
                            anchor.parentNode.insertBefore(switcher, anchor);
                        }
                    }
                    updateSubTypeTabs(window.selectedSubType);
                }

                // Clear link cache after new purchase so connection view reloads fresh
                subLinkCache.main = '';
                subLinkCache.whitelist = '';
                currentSubLink = '';
                window._subLinksPrefetched = false;
                const oldResult = document.getElementById('connection-result');
                if (oldResult) oldResult.remove();
                const oldPlaceholder = document.getElementById('conn-loading-placeholder');
                if (oldPlaceholder) oldPlaceholder.remove();

                if (window.syncNow) window.syncNow();
                showSuccessAnim(() => {
                    showModal({
                        title: 'Успешно!',
                        message: 'Подписка успешно оформлена. Теперь вы можете подключиться к нашим серверам.',
                        icon: 'check_circle',
                        actionText: 'К подключению',
                        onAction: () => {
                            window.activateTabById('view-connection', 'Подключение');
                        }
                    });
                });
            } else if (data.error === 'insufficient_funds') {
                hideLoading();
                handleTopup(Math.ceil(data.missing_amount), {
                    kind: 'buy',
                    tariffId: tariffId,
                    price: price,
                    userId: userId,
                    username: username,
                    replace: replace
                });
            } else if (data.error === 'tariff_change_locked') {
                hideLoading();
                showModal({
                    title: 'Смена недоступна',
                    message: 'Ваш текущий тариф нельзя сменить на другой.',
                    icon: 'lock',
                    actionText: 'Ок',
                    onAction: hideModal
                });
            } else {
                hideLoading();
                showModal({
                    title: 'Ошибка',
                    message: data.error || 'Произошла непредвиденная ошибка.',
                    icon: 'error',
                    actionText: 'Ок',
                    onAction: hideModal
                });
            }
        } catch (error) {
            hideLoading();
            showModal({
                title: 'Ошибка сети',
                message: 'Не удалось связаться с сервером.',
                icon: 'cloud_off',
                actionText: 'Ок',
                onAction: hideModal
            });
        }
    }

    window.handleBuy = async (tariffId, price, tariffName = '', tariffDays = 0) => {
        const tg = window.Telegram?.WebApp;
        const userId = window.authenticatedUserId;
        const username = tg?.initDataUnsafe?.user?.username || SAFE_MOCK_USER_DATA?.username;

        if (!userId || userId === 'undefined') {
            showModal({
                title: 'Ошибка',
                message: 'Ваш профиль еще не загружен. Пожалуйста, попробуйте снова через секунду.',
                icon: 'hourglass_empty',
                actionText: 'Ок',
                onAction: hideModal
            });
            return;
        }

        // If user already has an active subscription — show replacement confirmation
        if (window.HAS_ACTIVE_SUB) {
            const currentId = Number(window.CURRENT_TARIFF_ID || 0);
            const sameTariff = (currentId && Number(tariffId) === currentId)
                || (tariffName && window.CURRENT_TARIFF_NAME
                    && tariffName === window.CURRENT_TARIFF_NAME);
            if (window.TARIFF_CHANGE_LOCKED && !sameTariff) {
                showModal({
                    title: 'Смена недоступна',
                    message: 'Ваш текущий тариф нельзя сменить на другой. Продлить его можно кнопкой «Продлить подписку».',
                    icon: 'lock',
                    actionText: 'Ок',
                    onAction: hideModal
                });
                return;
            }

            const remainingDays = window.REMAINING_DAYS || 0;
            const currentName = window.CURRENT_TARIFF_NAME || 'Текущий тариф';

            const comparisonHtml = `
                <div style="width:100%;text-align:left;display:flex;flex-direction:column;gap:10px;">
                    <div style="background:rgba(255,255,255,0.05);border-radius:14px;padding:12px 14px;">
                        <div style="font-size:10px;color:var(--md-sys-color-primary);opacity:.8;text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;">Текущий тариф</div>
                        <div style="font-size:15px;font-weight:500;color:#E6E1E5;">${escapeHtml(currentName)}</div>
                        <div style="font-size:12px;color:rgba(230,225,229,.55);margin-top:3px;">Осталось: <b style="color:rgba(230,225,229,.85);">${remainingDays} дней</b></div>
                    </div>
                    <div style="display:flex;justify-content:center;">
                        <span class="material-symbols-rounded" style="color:var(--md-sys-color-primary);opacity:.5;font-size:20px;">arrow_downward</span>
                    </div>
                    <div style="background:rgba(208,188,255,.08);border:1px solid rgba(208,188,255,.18);border-radius:14px;padding:12px 14px;">
                        <div style="font-size:10px;color:var(--md-sys-color-primary);opacity:.8;text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;">Новый тариф</div>
                        <div style="font-size:15px;font-weight:500;color:#E6E1E5;">${escapeHtml(tariffName)}</div>
                        <div style="font-size:12px;color:rgba(230,225,229,.55);margin-top:3px;">${tariffDays} дней &middot; ${price} ₽</div>
                    </div>
                    <div style="background:rgba(239,83,80,.08);border-radius:12px;padding:10px 12px;display:flex;gap:8px;align-items:flex-start;">
                        <span class="material-symbols-rounded" style="color:#EF5350;font-size:16px;flex-shrink:0;margin-top:1px;">warning</span>
                        <span style="font-size:12px;color:rgba(230,225,229,.75);line-height:1.5;">Оставшиеся дни <b>пропадут</b>. Подписка начнётся заново с параметрами нового тарифа.</span>
                    </div>
                </div>`;

            showModal({
                title: 'Замена подписки',
                message: '',
                icon: 'swap_horiz',
                customHtml: comparisonHtml,
                actionText: 'Заменить тариф',
                closeBtnText: 'Оставить',
                onAction: () => {
                    performBuy(tariffId, price, userId, username, true);
                }
            });
            return;
        }

        // No active sub — just buy
        performBuy(tariffId, price, userId, username, false);
    };

    window.formatExpireDate = (isoString) => {
        if (!isoString) return '';
        const date = new Date(isoString);
        const months = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
        return `${date.getDate()} ${months[date.getMonth()]} ${date.getFullYear()}`;
    };

    window.formatBytes = (bytes) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    window.scrollToSubSlide = (index) => {
        const slider = document.getElementById('sub-slider');
        const dots = document.querySelectorAll('.sub-dot');
        if (!slider) return;
        
        const slideWidth = slider.clientWidth;
        slider.scrollTo({ left: slideWidth * index, behavior: 'smooth' });
        
        dots.forEach((dot, i) => {
            if (i === index) dot.classList.add('active');
            else dot.classList.remove('active');
        });
    };

    // Attach scroll listener to sync dots automatically
    function initSubSlider() {
        const el = document.getElementById('sub-slider');
        if (!el || el._sliderInit) return;
        el._sliderInit = true;

        function snapToNearestSlide() {
            const slideWidth = el.clientWidth;
            const index = Math.round(el.scrollLeft / slideWidth);
            el.scrollTo({
                left: slideWidth * index,
                behavior: 'smooth'
            });
            const dots = document.querySelectorAll('.sub-dot');
            dots.forEach((dot, i) => {
                if (i === index) dot.classList.add('active');
                else dot.classList.remove('active');
            });
        }

        el.addEventListener('scroll', () => {
            const index = Math.round(el.scrollLeft / el.clientWidth);
            const dots = document.querySelectorAll('.sub-dot');
            dots.forEach((dot, i) => {
                if (i === index) dot.classList.add('active');
                else dot.classList.remove('active');
            });
        });

        el.addEventListener('click', (e) => {
            if (document._subSliderDidDrag) {
                e.preventDefault();
                e.stopPropagation();
                document._subSliderDidDrag = false;
            }
        }, true);
    }

    // Document-level drag listeners (added once, always work for current slider)
    if (!document._subSliderDragInit) {
        document._subSliderDragInit = true;
        let isDragging = false;
        let startX, scrollLeft;

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const el = document.getElementById('sub-slider');
            if (!el) return;
            const dx = e.pageX - startX;
            if (Math.abs(dx) > 3) document._subSliderDidDrag = true;
            if (document._subSliderDidDrag) {
                el.scrollLeft = scrollLeft - dx;
            }
        });

        document.addEventListener('mouseup', () => {
            if (!isDragging) return;
            isDragging = false;
            const el = document.getElementById('sub-slider');
            if (el) el.classList.remove('dragging');
            if (document._subSliderDidDrag) {
                const slideWidth = el ? el.clientWidth : 0;
                const index = Math.round((el ? el.scrollLeft : 0) / slideWidth);
                el && el.scrollTo({ left: slideWidth * index, behavior: 'smooth' });
                const dots = document.querySelectorAll('.sub-dot');
                dots.forEach((dot, i) => {
                    if (i === index) dot.classList.add('active');
                    else dot.classList.remove('active');
                });
            }
        });

        document.addEventListener('mousedown', (e) => {
            const el = document.getElementById('sub-slider');
            if (!el || !el.contains(e.target)) return;
            isDragging = true;
            document._subSliderDidDrag = false;
            startX = e.pageX;
            scrollLeft = el.scrollLeft;
            el.classList.add('dragging');
            e.preventDefault();
        }, true);
    }
    initSubSlider();

    window.toggleExtendMenu = (subType = 'main') => {
        if (!window.CURRENT_TARIFF_PRICE || !window.CURRENT_TARIFF_DAYS) {
            // Раньше тут был молчаливый return — кнопка «умирала» без
            // объяснений (например, когда profile.tarif пуст в БД).
            showModal({
                title: 'Не получилось открыть продление',
                message: 'Данные тарифа ещё загружаются или недоступны. '
                    + 'Обновите данные и попробуйте снова.',
                icon: 'hourglass_empty',
                actionText: 'Обновить',
                onAction: () => {
                    hideModal();
                    if (window.syncNow) window.syncNow();
                },
                closeBtnText: 'Закрыть'
            });
            return;
        }

        let basePrice = window.CURRENT_TARIFF_PRICE;
        let baseDays = window.CURRENT_TARIFF_DAYS;
        let title = 'Продление основной подписки';
        
        if (subType === 'whitelist') {
            basePrice = 100; // Fixed price for whitelist extension (can be dynamic if needed)
            baseDays = 30;
            title = 'Продление дополнительной подписки';
        }

        const pricePerMonth = (basePrice / baseDays) * 30;

        const options = [
            { months: 1, label: '1 месяц' },
            { months: 3, label: '3 месяца' },
            { months: 6, label: '6 месяцев' },
            { months: 12, label: '1 год' }
        ];

        let gridHtml = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; width: 100%;">';
        options.forEach(opt => {
            const optionPrice = Math.round(pricePerMonth * opt.months);
            gridHtml += `
                <button class="extend-option bounce" onclick="window.handleExtend(${opt.months}, ${optionPrice}, '${subType}')" style="width: 100%; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.05); border-radius: 12px; padding: 12px; display: flex; flex-direction: column; align-items: center; gap: 4px;">
                    <span class="ext-months" style="font-size: 14px; font-weight: 500; color: #E6E1E5;">${opt.label}</span>
                    <span class="ext-price" style="font-size: 13px; color: var(--md-sys-color-primary); font-weight: 600;">${optionPrice} ₽</span>
                </button>
            `;
        });
        gridHtml += '</div>';

        showModal({
            title: title,
            message: 'Выберите срок продления:',
            icon: 'update',
            customHtml: gridHtml,
            actionText: 'Отмена',
            onAction: null
        });
    };

    async function performExtend(months, subType = 'main') {
        const tg = window.Telegram?.WebApp;
        const userId = window.authenticatedUserId;

                if (!userId || userId === 'undefined') {
                    showModal({
                        title: 'Ошибка',
                        message: 'Ваш профиль еще не загружен.',
                        icon: 'error',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                    return;
                }

                showLoading('Продление подписки...');

                try {
                    const formData = new FormData();
                    formData.append('months', months);
                    formData.append('sub_type', subType);
                    formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

                    if (tg?.initData) {
                        formData.append('init_data', tg.initData);
                    }

                    const response = await fetch('/shop/extend-sub-api/', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok && data.success) {
                        // Use sync to get accurate data
                        if (window.syncNow) window.syncNow();

                        const newExpireAt = data.new_expire_at;
                        const newRemainingDays = data.remaining_days;
                        const newExpireDate = newExpireAt ? new Date(newExpireAt) : null;
                        const months_names = ['янв','фев','мар','апр','мая','июн','июл','авг','сен','окт','ноя','дек'];
                        const expireStr = newExpireDate
                            ? `${newExpireDate.getDate()} ${months_names[newExpireDate.getMonth()]} ${newExpireDate.getFullYear()}`
                            : '';

                        // Update main subscription card
                        window.REMAINING_DAYS = newRemainingDays;
                        const statusTextEl = document.getElementById('sub-status-text');
                        const statusEl = statusTextEl?.closest('.sub-status-minimal');
                        if (statusTextEl && expireStr) {
                            statusTextEl.innerHTML = `До ${expireStr} &bull; ${newRemainingDays} дн.`;
                        }
                        if (statusEl) {
                            statusEl.className = 'sub-status-minimal ' + (newRemainingDays > 3 ? 'status-active' : newRemainingDays > 0 ? 'status-expiring' : 'status-expired');
                        }
                        // Update whitelist card too (both extended)
                        const wlStatusTextEl = document.getElementById('wl-status-text');
                        const wlStatusEl = wlStatusTextEl?.closest('.sub-status-minimal');
                        if (wlStatusTextEl && expireStr) {
                            wlStatusTextEl.innerHTML = `До ${expireStr} &bull; ${newRemainingDays} дн.`;
                        }
                        if (wlStatusEl) {
                            wlStatusEl.className = 'sub-status-minimal ' + (newRemainingDays > 3 ? 'status-active' : newRemainingDays > 0 ? 'status-expiring' : 'status-expired');
                        }
                        window.CURRENT_TARIFF_DAYS = (window.CURRENT_TARIFF_DAYS || 30) + months * 30;

                        // Update balance
                        const balanceEl = document.getElementById('profile-balance');
                        if (balanceEl && data.new_balance !== undefined) {
                            balanceEl.textContent = `${data.new_balance.toFixed(0)} ₽`;
                        }

                        showSuccessAnim(() => {
                            showModal({
                                title: 'Успешно!',
                                message: `Подписка продлена на ${months} мес.`,
                                icon: 'check_circle',
                                actionText: 'Ок',
                                onAction: hideModal
                            });
                        });
                    } else if (data.error === 'insufficient_funds') {
                        hideLoading();
                        handleTopup(Math.ceil(data.missing_amount), {
                            kind: 'extend',
                            months: months,
                            subType: subType
                        });
                    } else {
                        hideLoading();
                        showModal({
                            title: 'Ошибка',
                            message: data.error || 'Произошла непредвиденная ошибка.',
                            icon: 'error',
                            actionText: 'Ок',
                            onAction: hideModal
                        });
                    }
                } catch (error) {
                    hideLoading();
                    showModal({
                        title: 'Ошибка сети',
                        message: 'Не удалось связаться с сервером.',
                        icon: 'cloud_off',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                }
    }

    window.handleExtend = (months, price, subType = 'main') => {
        showModal({
            title: 'Подтверждение',
            message: `Продлить подписку на ${months} мес. за ${price} ₽? Сумма будет списана с вашего баланса.`,
            icon: 'update',
            actionText: 'Продлить',
            onAction: async () => {
                hideModal();
                await performExtend(months, subType);
            }
        });
    };

    async function performWhitelistTopup() {
        const gbAmount = 5;
        const price = 150; // 150 RUB for 5GB
        const tg = window.Telegram?.WebApp;
                
                showLoading('Покупка трафика...');
                try {
                    const formData = new FormData();
                    formData.append('gb_amount', gbAmount);
                    formData.append('csrfmiddlewaretoken', CSRF_TOKEN);
                    if (tg?.initData) formData.append('init_data', tg.initData);

                    const response = await fetch('/shop/topup-whitelist-traffic-api/', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    
                    if (response.ok && data.success) {
                        if (window.syncNow) window.syncNow();
                        showSuccessAnim(() => {
                            showModal({
                                title: 'Успешно!',
                                message: `Трафик успешно добавлен.`,
                                icon: 'check_circle',
                                actionText: 'Ок',
                                onAction: hideModal
                            });
                        });
                    } else if (data.error === 'insufficient_funds') {
                        hideLoading();
                        handleTopup(Math.ceil(data.missing_amount), {kind: 'wl'});
                    } else {
                        hideLoading();
                        showModal({
                            title: 'Ошибка',
                            message: data.error || 'Ошибка при покупке трафика.',
                            icon: 'error',
                            actionText: 'Ок',
                            onAction: hideModal
                        });
                    }
                } catch (error) {
                    hideLoading();
                    showModal({
                        title: 'Ошибка сети',
                        message: 'Не удалось связаться с сервером.',
                        icon: 'cloud_off',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                }
    }

    window.handleTopupWhitelistTraffic = () => {
        const gbAmount = 5;
        const price = 150; // 150 RUB for 5GB
        showModal({
            title: 'Докупка трафика',
            message: `Купить ${gbAmount} ГБ трафика для дополнительной подписки за ${price} ₽?`,
            icon: 'add_circle',
            actionText: 'Купить',
            onAction: async () => {
                hideModal();
                await performWhitelistTopup();
            }
        });
    };

    const subLinkCache = { main: '', whitelist: '' };
    let currentSubLink = '';
    window.selectedSubType = 'main';

    window.hasActiveSubscription = () => {
        if (window.OPTIMISTIC_HAS_SUB) return true;
        if (window.HAS_ACTIVE_SUB) return true;
        return !!(window.REMAINING_DAYS && window.REMAINING_DAYS > 0);
    };

    // Eagerly fetch subscription link(s) in the background after the first
    // sync so the "Подключение" tab is ready without waiting for a click.
    async function prefetchSubLinks() {
        if (window._subLinksPrefetched) return;
        if (!window.authenticatedUserId) return;
        if (!window.hasActiveSubscription()) return;
        window._subLinksPrefetched = true;
        const types = ['main'];
        if (window.HAS_WHITELIST_SUB) types.push('whitelist');
        for (const type of types) {
            if (!subLinkCache[type] && !window._connectFetching) {
                await window.handleConnect({ silent: true, subType: type });
            }
        }
    }

    function showConnContent() {
        const content = document.getElementById('conn-content');
        if (content) content.style.display = 'flex';
    }

    function hideConnContent() {
        const content = document.getElementById('conn-content');
        if (content) content.style.display = 'none';
    }

    function renderSubLink(link) {
        currentSubLink = link;
        const qrCanvas = document.getElementById('qr-code-canvas');
        if (qrCanvas && window.QRious) {
            new QRious({
                element: qrCanvas,
                value: link,
                size: 160,
                level: 'M',
                background: 'white',
                foreground: 'black'
            });
        }
        showConnContent();
    }

    // Generation token so rapid switching cancels stale animation steps.
    let switchAnimToken = 0;
    let lastShownSubType = 'main';
    let switchInProgress = false;

    function animateResultIn(resultDiv, fromX, fromY) {
        if (!resultDiv) return;
        const token = switchAnimToken;
        resultDiv.classList.remove('hiding');
        resultDiv.classList.add('animate-in');
        resultDiv.style.transition = 'none';
        resultDiv.style.opacity = '0';
        resultDiv.style.transform = `translate(${fromX || 0}px, ${fromY || 0}px) scale(0.98)`;
        void resultDiv.offsetWidth;
        resultDiv.style.transition =
            'opacity 0.28s cubic-bezier(0.4, 0, 0.2, 1), transform 0.28s cubic-bezier(0.4, 0, 0.2, 1)';
        resultDiv.style.opacity = '1';
        resultDiv.style.transform = 'translate(0, 0) scale(1)';
        setTimeout(() => {
            if (token !== switchAnimToken) return;
            resultDiv.style.transition = '';
            resultDiv.style.opacity = '';
            resultDiv.style.transform = '';
        }, 300);
    }

    function animateResultOut(resultDiv, toX, toY, callback) {
        if (!resultDiv) {
            if (callback) callback();
            return;
        }
        const token = switchAnimToken;
        resultDiv.classList.remove('animate-in');
        resultDiv.style.transition = 'none';
        resultDiv.style.opacity = '1';
        resultDiv.style.transform = 'translate(0, 0) scale(1)';
        void resultDiv.offsetWidth;
        resultDiv.style.transition =
            'opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1), transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)';
        resultDiv.style.opacity = '0';
        resultDiv.style.transform = `translate(${toX || 0}px, ${toY || 0}px) scale(0.98)`;
        setTimeout(() => {
            if (token !== switchAnimToken) return;
            resultDiv.style.transition = '';
            resultDiv.style.opacity = '';
            resultDiv.style.transform = '';
            if (callback) callback();
        }, 220);
    }

    function updateSubTypeTabs(type) {
        const mainBtn = document.getElementById('sub-type-main');
        const wlBtn = document.getElementById('sub-type-whitelist');
        const indicator = document.querySelector('.sub-type-indicator');
        if (mainBtn && wlBtn) {
            if (type === 'main') {
                mainBtn.classList.add('active');
                wlBtn.classList.remove('active');
                if (indicator) indicator.classList.remove('whitelist');
            } else {
                wlBtn.classList.add('active');
                mainBtn.classList.remove('active');
                if (indicator) indicator.classList.add('whitelist');
            }
        }
    }

    function showSubType(type) {
        window.selectedSubType = type;
        updateSubTypeTabs(type);

        // Slide in the direction of the tab being switched to:
        // main -> whitelist pushes left, whitelist -> main pushes right.
        switchAnimToken++;
        switchInProgress = true;
        const goingRight = type === 'main';
        const outX = goingRight ? 24 : -24;

        const resultDiv = document.getElementById('connection-result');
        animateResultOut(resultDiv, outX, 0, () => {
            if (window.selectedSubType !== type) return;
            switchInProgress = false;
            lastShownSubType = type;
            currentSubLink = '';
            hideConnContent();
            if (resultDiv) {
                resultDiv.classList.remove('animate-in');
                resultDiv.classList.remove('hiding');
            }
            const cachedLink = subLinkCache[type];
            if (cachedLink) {
                renderSubLink(cachedLink);
                animateResultIn(resultDiv, -outX, 0);
            } else if (window.handleConnect && !window._connectFetching) {
                // Fallback for a link that wasn't prefetched yet (e.g. no sync).
                window.handleConnect({ fromX: -outX, fromY: 0 });
            }
        });
    }

    window.switchSubType = (type) => {
        // Ignore clicks on the tab that is already shown.
        if (type === lastShownSubType && !switchInProgress) return;
        showSubType(type);
    };

    window.copySubLink = () => {
        if (!currentSubLink) return;
        const tempInput = document.createElement('input');
        tempInput.value = currentSubLink;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
        }

        showModal({
            title: 'Ссылка скопирована!',
            message: 'Ссылка для подключения успешно скопирована в буфер обмена.',
            icon: 'content_copy',
            actionText: 'Ок',
            onAction: hideModal
        });
    };

    window.openSubLink = () => {
        if (!currentSubLink) return;
        const app = APP_DATA[window._selectedApp] || APP_DATA.incy;
        const deepLink = (app.scheme || 'happ://add/') + currentSubLink;

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.openLink) {
            // Inside Telegram Mini App: <app>:// can't be opened directly from WebView.
            // Open our server-side redirect page in the system browser via Telegram API —
            // the system browser handles the <app>:// deep link correctly.
            const redirectUrl = window.location.origin
                + '/connect/open-sub/?app='
                + encodeURIComponent(window._selectedApp)
                + '&link='
                + encodeURIComponent(currentSubLink);
            window.Telegram.WebApp.openLink(redirectUrl, { try_instant_view: false });
        } else {
            // Regular browser: direct deep link works fine
            window.location.href = deepLink;
        }
    };

    window.openSupport = (el) => {
        const url = el && el.getAttribute('data-url');
        if (!url) return;

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.openLink) {
            window.Telegram.WebApp.openLink(url);
        } else {
            window.open(url, '_blank');
        }
    };

    window.connectAndSwitch = (subType) => {
        const type = subType || 'main';
        window.selectedSubType = type;
        updateSubTypeTabs(type);
        window.activateTabById('view-connection', 'Подключение');
        setTimeout(() => {
            showSubType(type);
            if (subLinkCache[type] && window.authenticatedUserId) {
                window.showInstructions();
            }
        }, 450);
    };

    window.handleConnect = async (options = {}) => {
        if (window._connectFetching) return;
        window._connectFetching = true;

        const fromX = options.fromX || 0;
        const fromY = options.fromY === undefined ? 12 : options.fromY;
        const silent = !!options.silent;
        const subType = options.subType || window.selectedSubType || 'main';
        const tg = window.Telegram?.WebApp;
        const userId = window.authenticatedUserId;

        if (!userId || userId === 'undefined') {
            window._connectFetching = false;
            if (!silent) {
                showModal({
                    title: 'Ошибка',
                    message: 'Ваш профиль еще не загружен. Пожалуйста, подождите секунду и попробуйте снова.',
                    icon: 'hourglass_empty',
                    actionText: 'Ок',
                    onAction: hideModal
                });
            }
            return;
        }

        const placeholder = document.getElementById('conn-loading-placeholder');
        const resultDiv = document.getElementById('connection-result');
        // Only touch the visible area when we'll actually render this sub-type,
        // so silent background prefetches don't disturb the QR that is shown.
        const willRender = window.selectedSubType === subType;
        if (willRender) {
            hideConnContent();
            if (placeholder) placeholder.style.display = 'flex';
            if (resultDiv) {
                resultDiv.classList.remove('animate-in');
                resultDiv.classList.remove('hiding');
            }
        }

        try {
            const formData = new FormData();
            if (tg?.initData) {
                formData.append('init_data', tg.initData);
            }
            formData.append('sub_type', subType);
            formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

            const response = await fetch('/shop/get-sub-link-api/', {
                method: 'POST',
                body: formData,
            });

            let data;
            try {
                data = await response.json();
            } catch (e) {
                throw new Error('Invalid JSON response');
            }

            if (placeholder && willRender) placeholder.style.display = 'none';

            if (response.ok && data.success && data.link) {
                subLinkCache[subType] = data.link;
                // Ignore stale responses if the user switched sub-type mid-fetch.
                if (willRender) {
                    renderSubLink(data.link);
                    animateResultIn(resultDiv, fromX, fromY);
                }
            } else {
                if (placeholder && willRender) placeholder.style.display = 'none';
                if (!silent) {
                    showModal({
                        title: 'Ошибка',
                        message: data.error || 'У вас нет активной подписки.',
                        icon: 'error',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                }
            }
        } catch (error) {
            if (placeholder && willRender) placeholder.style.display = 'none';
            console.error('handleConnect error:', error);
            if (!silent) {
                showModal({
                    title: 'Ошибка',
                    message: 'Не удалось получить ссылку. Проверьте интернет-соединение или попробуйте позже.',
                    icon: 'cloud_off',
                    actionText: 'Ок',
                    onAction: hideModal
                });
            }
        } finally {
            window._connectFetching = false;
            // If the sub-type changed while this request was in flight,
            // fetch the link for the now-selected sub-type.
            if (!silent && window.selectedSubType !== subType) {
                window.handleConnect({ fromX: 20, fromY: 0 });
            }
        }
    };

    window.handleSetNodeStatus = (nodeId, nodeDataStr) => {
        const node = JSON.parse(decodeURIComponent(nodeDataStr));
        const tg = window.Telegram?.WebApp;
        const userId = window.authenticatedUserId;

        if (!userId || userId === 'undefined') {
            alert('Профиль не загружен');
            return;
        }

        const customHtml = `
            <div style="display: flex; flex-direction: column; gap: 12px; margin-top: 15px; text-align: left;">
                <label class="bounce" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: rgba(255,255,255,0.05); border-radius: 16px; cursor: pointer;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span class="material-symbols-rounded" style="color: var(--md-sys-color-primary);">tune</span>
                        <span style="font-size: 14px; font-weight: 500;">Ручное управление</span>
                    </div>
                    <div class="switch-ui">
                        <input type="checkbox" id="modal-use-manual" ${node.use_manual_status ? 'checked' : ''} style="display: none;">
                        <span class="slider round"></span>
                    </div>
                </label>
                
                <label id="manual-online-wrapper" class="bounce" style="display: ${node.use_manual_status ? 'flex' : 'none'}; align-items: center; justify-content: space-between; padding: 12px 16px; background: rgba(255,255,255,0.05); border-radius: 16px; cursor: pointer;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span class="material-symbols-rounded" id="manual-online-icon" style="color: ${node.manual_is_online ? '#4CAF50' : '#F44336'};">
                            ${node.manual_is_online ? 'cloud_done' : 'cloud_off'}
                        </span>
                        <span style="font-size: 14px; font-weight: 500;" id="manual-online-text">
                            ${node.manual_is_online ? 'Статус: ОНЛАЙН' : 'Статус: ОФФЛАЙН'}
                        </span>
                    </div>
                    <div class="switch-ui">
                        <input type="checkbox" id="modal-manual-online" ${node.manual_is_online ? 'checked' : ''} style="display: none;">
                        <span class="slider round"></span>
                    </div>
                </label>
            </div>
            <style>
                .switch-ui { position: relative; display: inline-block; width: 40px; height: 22px; pointer-events: none; }
                .slider { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(255,255,255,0.1); transition: .4s; border-radius: 34px; }
                .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
                input:checked + .slider { background-color: var(--md-sys-color-primary); }
                input:checked + .slider:before { transform: translateX(18px); }
            </style>
        `;

        showModal({
            title: 'Статус сервера',
            message: `Настройте параметры ноды #${nodeId}:`,
            icon: 'dns',
            actionText: 'Сохранить',
            showInput: true,
            inputValue: node.custom_status || '',
            inputPlaceholder: 'Кастомный текст статуса...',
            customHtml: customHtml,
            onAction: async () => {
                const statusText = modalAmountInput.value;
                const useManual = document.getElementById('modal-use-manual').checked;
                const manualOnline = document.getElementById('modal-manual-online').checked;

                try {
                    const formData = new FormData();
                    formData.append('node_id', nodeId);
                    formData.append('status_text', statusText);
                    formData.append('use_manual_status', useManual);
                    formData.append('manual_is_online', manualOnline);

                    if (tg?.initData) {
                        formData.append('init_data', tg.initData);
                    }

                    const response = await fetch('/connect/set-node-status-api/', {
                        method: 'POST',
                        body: formData
                    });

                    if (response.ok) {
                        if (window.syncNow) window.syncNow();
                    } else {
                        alert('Ошибка сохранения статуса');
                    }
                } catch (e) {
                    console.error('Failed to set node status:', e);
                }
            }
        });

        // Event listeners for switches
        const useManualCheck = document.getElementById('modal-use-manual');
        const manualOnlineCheck = document.getElementById('modal-manual-online');
        const manualOnlineWrapper = document.getElementById('manual-online-wrapper');
        const onlineIcon = document.getElementById('manual-online-icon');
        const onlineText = document.getElementById('manual-online-text');

        if (useManualCheck) {
            useManualCheck.onchange = (e) => {
                manualOnlineWrapper.style.display = e.target.checked ? 'flex' : 'none';
            };
        }

        if (manualOnlineCheck) {
            manualOnlineCheck.onchange = (e) => {
                const isOnline = e.target.checked;
                onlineIcon.style.color = isOnline ? '#4CAF50' : '#F44336';
                onlineIcon.textContent = isOnline ? 'cloud_done' : 'cloud_off';
                onlineText.textContent = isOnline ? 'Статус: ОНЛАЙН' : 'Статус: ОФФЛАЙН';
            };
        }
    };

    async function performBuySlot() {
        const tg = window.Telegram?.WebApp;

        showLoading('Покупка слота...');
                try {
                    const formData = new FormData();
                    formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

                    if (tg?.initData) {
                        formData.append('init_data', tg.initData);
                    }

                    const response = await fetch('/shop/buy-slot-api/', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok) {
                        const balanceAmount = document.getElementById('profile-balance');
                        if (balanceAmount) {
                            balanceAmount.textContent = `${data.new_balance.toFixed(0)} ₽`;
                        }
                        if (window.syncNow) window.syncNow();
                        showSuccessAnim(() => {
                            if (window.syncNow) window.syncNow();
                        });
                    } else if (data.error === 'insufficient_funds') {
                        hideLoading();
                        handleTopup(Math.ceil(data.missing_amount), {kind: 'slot'});
                    } else {
                        hideLoading();
                        showModal({
                            title: 'Ошибка',
                            message: data.error || 'Ошибка покупки слота.',
                            icon: 'error',
                            actionText: 'Ок',
                            onAction: hideModal
                        });
                    }
                } catch (e) {
                    hideLoading();
                    showModal({
                        title: 'Ошибка сети',
                        message: 'Не удалось связаться с сервером.',
                        icon: 'cloud_off',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                }
    }

    window.handleBuySlot = async () => {
        const userId = window.authenticatedUserId;

        if (!userId || userId === 'undefined') {
            showModal({
                title: 'Ошибка',
                message: 'Ваш профиль еще не загружен.',
                icon: 'error',
                actionText: 'Ок',
                onAction: hideModal
            });
            return;
        }

        showModal({
            title: 'Купить доп. слот',
            message: 'Вы уверены, что хотите купить дополнительный слот для устройства за 100 ₽?',
            icon: 'person_add',
            actionText: 'Подтвердить',
            onAction: async () => {
                await performBuySlot();
            }
        });
    };

    window.handleDeleteDevice = (hwid, rowIndex) => {
        showModal({
            title: 'Удалить устройство?',
            message: 'Это устройство будет удалено из вашего списка. При следующем подключении оно снова зарегистрируется автоматически.',
            icon: 'delete_outline',
            actionText: 'Удалить',
            onAction: async () => {
                hideModal();
                const tg = window.Telegram?.WebApp;
                const userId = window.authenticatedUserId;

                if (!userId || userId === 'undefined') {
                    showModal({
                        title: 'Ошибка',
                        message: 'Ваш профиль еще не загружен.',
                        icon: 'error',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                    return;
                }

                showLoading('Удаление устройства...');

                try {
                    const formData = new FormData();
                    formData.append('hwid', hwid);
                    formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

                    if (tg?.initData) {
                        formData.append('init_data', tg.initData);
                    }

                    const response = await fetch('/shop/delete-hwid-device-api/', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok && data.success) {
                        const row = document.getElementById(`device-row-${rowIndex}`);
                        const container = document.getElementById('devices-list-container');
                        const countEl = document.getElementById('devices-count-display');

                        if (row) {
                            const h = row.offsetHeight;
                            row.style.overflow = 'hidden';
                            row.style.maxHeight = h + 'px';
                            row.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                            row.style.opacity = '0';
                            row.style.transform = 'translateX(40px)';
                            await new Promise(r => setTimeout(r, 300));
                            row.style.transition = 'max-height 0.3s ease';
                            row.style.maxHeight = '0';
                            const divider = row.nextElementSibling?.classList.contains('settings-divider')
                                ? row.nextElementSibling
                                : row.previousElementSibling?.classList.contains('settings-divider')
                                    ? row.previousElementSibling : null;
                            if (divider) {
                                divider.style.transition = 'opacity 0.25s ease, max-height 0.25s ease';
                                divider.style.opacity = '0';
                                divider.style.maxHeight = '0';
                            }
                            await new Promise(r => setTimeout(r, 300));
                        }

                        const totalDevices = container ? container.querySelectorAll('.device-row').length : 0;
                        const remaining = totalDevices - 1;
                        const limit = countEl ? (countEl.textContent.match(/\/\s*(\d+)/)?.[1] || '0') : '0';

                        if (countEl) {
                            countEl.innerHTML = `
                                <span class="material-symbols-rounded" style="font-size: 14px;">devices</span>
                                ${Math.max(0, remaining)} / ${limit}`;
                        }

                        if (container) {
                            container.style.transition = 'opacity 0.2s ease';
                            container.style.opacity = '0';
                            await new Promise(r => setTimeout(r, 200));

                            if (remaining <= 0) {
                                container.innerHTML = `
                                    <div class="settings-empty">
                                        <span class="material-symbols-rounded">devices_off</span>
                                        <span>Нет подключённых устройств</span>
                                    </div>`;
                            } else {
                                const toRemove = container.querySelector(`#device-row-${rowIndex}`);
                                if (toRemove) {
                                    const d = toRemove.nextElementSibling?.classList.contains('settings-divider')
                                        ? toRemove.nextElementSibling
                                        : toRemove.previousElementSibling?.classList.contains('settings-divider')
                                            ? toRemove.previousElementSibling : null;
                                    toRemove.remove();
                                    if (d) d.remove();
                                }
                            }
                            requestAnimationFrame(() => {
                                container.style.opacity = '1';
                            });
                        }

                        showSuccessAnim();
                    } else {
                        hideLoading();
                        showModal({
                            title: 'Ошибка',
                            message: data.error || 'Не удалось удалить устройство.',
                            icon: 'error',
                            actionText: 'Ок',
                            onAction: hideModal
                        });
                    }
                } catch (e) {
                    hideLoading();
                    showModal({
                        title: 'Ошибка сети',
                        message: 'Не удалось связаться с сервером.',
                        icon: 'cloud_off',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                }
            }
        });
    };

    window.handleProxyConnect = (url, name) => {
        if (!url) return;

        showModal({
            title: 'Telegram Прокси',
            message: `Вы собираетесь подключить прокси "${name}". Это позволит Telegram работать стабильнее.`,
            icon: 'send',
            actionText: 'Подключить',
            onAction: () => {
                if (window.Telegram && window.Telegram.WebApp) {
                    if (url.includes('t.me/') || url.startsWith('tg://')) {
                        window.Telegram.WebApp.openTelegramLink(url);
                    } else {
                        window.Telegram.WebApp.openLink(url);
                    }
                } else {
                    window.open(url, '_blank');
                }
            }
        });
    };

    window.copyProxyLink = (url) => {
        if (!url) return;
        const tempInput = document.createElement('input');
        tempInput.value = url;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
        }

        showModal({
            title: 'Ссылка скопирована!',
            message: 'Ссылка на прокси успешно скопирована.',
            icon: 'content_copy',
            actionText: 'Ок',
            onAction: hideModal
        });
    };

    // Data Synchronization Logic
    function updateUIWithSyncData(data) {
        if (!data.success) return;

        if (data.topup_bonuses) window._topupBonuses = data.topup_bonuses;

        // Update Balance and Profile Details
        if (data.profile) {
            const balanceEl = document.getElementById('profile-balance');
            if (balanceEl) balanceEl.textContent = `${data.profile.balance.toFixed(0)} ₽`;

            if (window._lastBalance !== null && window._lastBalance !== data.profile.balance) {
                window._historyLoaded = false;
            }
            window._lastBalance = data.profile.balance;

            const tarifNameEl = document.getElementById('profile-tarif-name');
            if (tarifNameEl) tarifNameEl.textContent = data.profile.tarif_name;

            // Update global tariff variables for Extension menu.
            // Без тарифа в БД — сбрасываем в 0, чтобы меню продления
            // показывало ошибку, а не считало по протухшей цене.
            if (data.profile.tariff_id) {
                if (data.profile.tarif_price) window.CURRENT_TARIFF_PRICE = data.profile.tarif_price;
                if (data.profile.tarif_days) window.CURRENT_TARIFF_DAYS = data.profile.tarif_days;
            } else {
                window.CURRENT_TARIFF_PRICE = 0;
                window.CURRENT_TARIFF_DAYS = 0;
            }

            // Update HAS_ACTIVE_SUB flag
            // Use OR with OPTIMISTIC_HAS_SUB to avoid flickering right after purchase
            // An RW record is not enough: expired users remain in the panel.
            // On rw_error keep previous state — transient API failure must not hide the sub
            if (!data.rw_error) {
                const expireAt = data.rw_user?.expireAt || data.rw_user?.expire_at;
                const hasValidExpiry = expireAt && Date.parse(expireAt) > Date.now();
                window.HAS_ACTIVE_SUB = (!!data.rw_user && hasValidExpiry) || !!window.OPTIMISTIC_HAS_SUB;
                if (data.rw_user) {
                    window.CURRENT_TARIFF_NAME = data.profile.tarif_name;
                    window.OPTIMISTIC_HAS_SUB = false; // Reset once we have real data from Remnawave
                }

                // Кнопка своего тарифа: сервер рендерит disabled «Уже активен»
                // без учёта expiry. Истёкшую подписку можно купить снова —
                // включаем кнопку как «Продлить», активную — гасим обратно.
                const ownedId = Number(data.profile.tariff_id || 0);
                const ownedBtn = ownedId
                    ? document.querySelector(`.tariff-card-v2[data-tariff-id="${ownedId}"] .v2-buy-btn`)
                    : null;
                if (ownedBtn && (ownedBtn.getAttribute('onclick') || '').includes('handleBuy')) {
                    if (hasValidExpiry) {
                        ownedBtn.disabled = true;
                        ownedBtn.textContent = 'Уже активен';
                    } else {
                        ownedBtn.disabled = false;
                        ownedBtn.textContent = 'Продлить';
                    }
                }
            }

            // Update settings toggles
            const paymentReminderToggle = document.getElementById('toggle-payment-reminder');
            const notificationsToggle = document.getElementById('toggle-notifications');
            const serverNotificationsToggle = document.getElementById('toggle-server-notifications');
            if (paymentReminderToggle && data.profile.payment_reminder_enabled !== undefined) {
                paymentReminderToggle.checked = data.profile.payment_reminder_enabled;
            }
            if (notificationsToggle && data.profile.notifications_enabled !== undefined) {
                notificationsToggle.checked = data.profile.notifications_enabled;
            }
            if (serverNotificationsToggle && data.profile.server_notifications_enabled !== undefined) {
                serverNotificationsToggle.checked = data.profile.server_notifications_enabled;
            }
        }

        // Кэш рефералки из sync-data: модалка открывается мгновенно,
        // цифры обновляются каждым поллингом без отдельных запросов.
        if (data.referral && data.referral.link) {
            window._referralData = data.referral;
            window._referralLink = data.referral.link;
        }

        // Update Proxy
        const proxyContainer = document.getElementById('proxy-container');
        if (proxyContainer) {
            if (data.proxies && data.proxies.length > 0) {
                let proxiesHtml = `
                    <h3 style="color: var(--md-sys-color-primary); font-weight: 500; font-size: 14px; opacity: 0.8; letter-spacing: 0.5px; text-transform: uppercase; margin: 0;">Прокси</h3>`;
                data.proxies.forEach(proxy => {
                    proxiesHtml += `
                    <div class="proxy-section" style="margin-top: 10px; padding: 18px; background: var(--panel-bg); border-radius: 24px; position: relative; overflow: hidden; border: 1px solid rgba(255,255,255,0.05);">
                        <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 16px; position: relative; z-index: 1;">
                            <div style="width: 44px; height: 44px; border-radius: 14px; background: rgba(208, 188, 255, 0.08); color: var(--md-sys-color-primary); display: flex; align-items: center; justify-content: center;">
                                <span class="material-symbols-rounded" style="font-size: 24px;">send</span>
                            </div>
                            <div style="flex: 1;">
                                <div style="display: flex; align-items: center; gap: 6px;">
                                    <h4 style="margin: 0; font-size: 15px; font-weight: 500; color: #FFFFFF;">${escapeHtml(proxy.name)}</h4>
                                </div>
                                <span style="font-size: 12px; opacity: 0.5; color: #E6E1E5; display: block; margin-top: 2px;">Telegram Прокси</span>
                            </div>
                        </div>
                        
                        <div style="display: flex; gap: 10px; position: relative; z-index: 1;">
                            <button class="action-btn bounce" 
                                    style="flex: 1; height: 48px; background: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary); border-radius: 14px; font-weight: 600; font-size: 14px;" 
                                    onclick="handleProxyConnect('${escapeJsAttr(proxy.connection_url)}', '${escapeJsAttr(proxy.name)}')">
                                <span class="material-symbols-rounded" style="font-size: 20px;">bolt</span>
                                Подключить
                            </button>
                            <button class="action-btn bounce" 
                                    style="width: 48px; height: 48px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; display: flex; align-items: center; justify-content: center; padding: 0;" 
                                    onclick="copyProxyLink('${escapeJsAttr(proxy.connection_url)}')"
                                    title="Скопировать ссылку">
                                <span class="material-symbols-rounded" style="font-size: 20px; color: #FFFFFF; opacity: 0.7;">content_copy</span>
                            </button>
                        </div>
                    </div>`;
                });
                proxyContainer.innerHTML = proxiesHtml;
            } else {
                proxyContainer.innerHTML = '';
            }
        }

        // Update Subscription Cards in Tariffs View (Slider)
        const subContainer = document.getElementById('current-subscription-container');
        if (subContainer) {
            if (data.rw_error) {
                // Transient API error — keep existing cards, don't wipe the UI
                console.warn('Sync rw_user error, keeping previous subscription cards');
            } else if (data.rw_user && data.profile) {
                const remDays = data.rw_user.remaining_days || 0;
                const tariffName = data.profile.tarif_name || 'Premium';
                const devLimit = data.rw_user.hwidDeviceLimit || 0;
                const devCount = data.hwid_devices ? data.hwid_devices.length : 0;
                const expireAt = data.rw_user.expireAt || data.rw_user.expire_at || '';
                const expireStr = expireAt ? formatExpireDate(expireAt) : '';
                const statusClass = remDays > 3 ? 'status-active' : remDays > 0 ? 'status-expiring' : 'status-expired';
                const statusText = remDays > 0
                    ? `До <span>${expireStr}</span> &bull; ${remDays} дн.`
                    : 'Истекла';

                // If card structure missing (server rendered empty), rebuild it
                const subStatusText = document.getElementById('sub-status-text');
                if (!subStatusText) {
                    let sliderHtml = `
                        <div class="subscription-slider" id="sub-slider">
                            <div class="sub-slide bounce">
                                <div class="sub-header">
                                    <div class="sub-icon"><span class="material-symbols-rounded">verified_user</span></div>
                                    <div class="sub-info">
                                        <span class="sub-label">Основная подписка</span>
                                        <h3 class="sub-title" id="sub-title-display">${escapeHtml(tariffName)}</h3>
                                    </div>
                                </div>
                                <div class="sub-status-minimal ${statusClass}">
                                    <div class="status-dot"></div>
                                    <span id="sub-status-text">${statusText}</span>
                                </div>
                                <div class="sub-footer">
                                    <div class="sub-device-info">
                                        <span class="material-symbols-rounded" style="font-size: 16px;">devices</span>
                                        <span id="sub-device-text">${devCount} / ${devLimit} устройств</span>
                                        <button class="action-btn icon-btn bounce" onclick="activateTabById('view-settings','Настройки')" title="Настройки" aria-label="Настройки">
                                            <span class="material-symbols-rounded">brush</span>
                                        </button>
                                    </div>
                                    <div class="sub-actions">
                                        <button class="action-btn bounce extend-btn" onclick="toggleExtendMenu('main')">
                                            <span class="material-symbols-rounded">update</span>Продлить подписку
                                        </button>
                                        <button class="action-btn bounce connect-btn" onclick="connectAndSwitch('main')">
                                            <span class="material-symbols-rounded">vpn_key</span>Подключить
                                        </button>
                                    </div>
                                </div>
                            </div>`;

                    if (data.whitelist_user) {
                        const wlRem = data.whitelist_user.remaining_days || 0;
                        const wlExpire = data.whitelist_user.expireAt || data.whitelist_user.expire_at || '';
                        const wlExpStr = wlExpire ? formatExpireDate(wlExpire) : '';
                        const wlStatusClass = wlRem > 3 ? 'status-active' : wlRem > 0 ? 'status-expiring' : 'status-expired';
                        const wlStatusText = wlRem > 0
                            ? `До <span>${wlExpStr}</span> &bull; ${wlRem} дн.`
                            : 'Истекла';
                        sliderHtml += `
                            <div class="sub-slide bounce wl-slide">
                                <div class="sub-header">
                                    <div class="sub-icon wl-icon"><span class="material-symbols-rounded">shield_locked</span></div>
                                    <div class="sub-info">
                                        <span class="sub-label">Дополнительная подписка</span>
                                        <h3 class="sub-title">Расширенный доступ</h3>
                                        <span class="sub-label" style="font-size:11px; opacity:0.65; margin-top:2px; display:block;">Работает в условиях белых ограничений</span>
                                    </div>
                                </div>
                                <div class="sub-status-minimal ${wlStatusClass}">
                                    <div class="status-dot"></div>
                                    <span id="wl-status-text">${wlStatusText}</span>
                                </div>
                                <div class="wl-traffic-bar">
                                    <div class="wl-traffic-info">
                                        <span style="opacity:0.8; font-size:12px;">Трафик:</span>
                                        <span id="wl-traffic-text" style="font-size:12px; font-weight:500;">Загрузка...</span>
                                    </div>
                                    <div class="wl-progress-bg"><div class="wl-progress-fill" id="wl-traffic-progress"></div></div>
                                </div>
                                <div class="sub-footer">
                                    <div class="sub-actions">
                                        <button class="action-btn bounce extend-btn" style="background: rgba(76, 175, 80, 0.15); color: #4CAF50;" onclick="handleTopupWhitelistTraffic()">
                                            <span class="material-symbols-rounded">add_circle</span>+5 ГБ за 150 ₽
                                        </button>
                                        <button class="action-btn bounce connect-btn" onclick="connectAndSwitch('whitelist')">
                                            <span class="material-symbols-rounded">vpn_key</span>Подключить
                                        </button>
                                    </div>
                                </div>
                            </div>`;
                    }

                    sliderHtml += `</div>`;
                    if (data.whitelist_user) {
                        sliderHtml += `
                            <div class="sub-slider-dots" id="sub-slider-dots">
                                <div class="sub-dot active" onclick="scrollToSubSlide(0)"></div>
                                <div class="sub-dot" onclick="scrollToSubSlide(1)"></div>
                            </div>`;
                    }

                    subContainer.innerHTML = sliderHtml;
                    initSubSlider();
                } else {
                    // Card exists, update in-place
                    const subTitleEl = document.getElementById('sub-title-display');
                    if (subTitleEl) subTitleEl.textContent = tariffName;

                    const subStatusEl = subStatusText.closest('.sub-status-minimal');
                    subStatusText.innerHTML = statusText;
                    if (subStatusEl) subStatusEl.className = 'sub-status-minimal ' + statusClass;

                    const deviceTextEl = document.getElementById('sub-device-text');
                    if (deviceTextEl) deviceTextEl.textContent = `${devCount} / ${devLimit} устройств`;

                    // Whitelist slide
                    if (data.whitelist_user) {
                        window.HAS_WHITELIST_SUB = true;
                        const wlLimit = data.whitelist_user.trafficLimitBytes || 0;
                        const wlUsed = data.whitelist_user.userTraffic?.usedTrafficBytes || 0;
                        const trafficTextEl = document.getElementById('wl-traffic-text');
                        const trafficProgressEl = document.getElementById('wl-traffic-progress');
                        if (trafficTextEl) {
                            const remaining = Math.max(0, wlLimit - wlUsed);
                            trafficTextEl.textContent = `${formatBytes(remaining)} / ${formatBytes(wlLimit)}`;
                        }
                        if (trafficProgressEl && wlLimit > 0) {
                            const percent = Math.min(100, Math.max(0, (wlUsed / wlLimit) * 100));
                            trafficProgressEl.style.width = `${percent}%`;
                            if (percent > 90) trafficProgressEl.style.background = '#F44336';
                            else if (percent > 70) trafficProgressEl.style.background = '#FF9800';
                            else trafficProgressEl.style.background = '#4CAF50';
                        }
                        const wlRem = data.whitelist_user.remaining_days || 0;
                        const wlExpire = data.whitelist_user.expireAt || data.whitelist_user.expire_at || '';
                        const wlExpStr = wlExpire ? formatExpireDate(wlExpire) : '';
                        const wlStatusText = document.getElementById('wl-status-text');
                        const wlStatusEl = wlStatusText?.closest('.sub-status-minimal');
                        if (wlStatusText) {
                            wlStatusText.innerHTML = wlRem > 0
                                ? `До <span>${wlExpStr}</span> &bull; ${wlRem} дн.`
                                : 'Истекла';
                        }
                        if (wlStatusEl) {
                            wlStatusEl.className = 'sub-status-minimal ' + (wlRem > 3 ? 'status-active' : wlRem > 0 ? 'status-expiring' : 'status-expired');
                        }
                    } else if (!data.wl_error) {
                        // Whitelist sub truly absent (not a fetch error) — remove slide
                        const wlSlide = document.querySelector('.wl-slide');
                        if (wlSlide) wlSlide.remove();
                        const dotsContainer = document.getElementById('sub-slider-dots');
                        if (dotsContainer) dotsContainer.style.display = 'none';
                        window.HAS_WHITELIST_SUB = false;
                    }
                }

                window.REMAINING_DAYS = remDays;
                window.CURRENT_TARIFF_NAME = tariffName;
                window.CURRENT_TARIFF_PRICE = parseFloat(data.profile.tarif_price || 0);
                window.CURRENT_TARIFF_DAYS = parseInt(data.profile.tarif_days || 30);
                window.HAS_ACTIVE_SUB = remDays > 0;
                window.CURRENT_TARIFF_ID = data.profile.tariff_id || 0;
                window.TARIFF_CHANGE_LOCKED = !!data.profile.tariff_change_locked;
            } else {
                subContainer.innerHTML = '';
            }
        }

        // Update Connection View Status
        const connectionSubInfo = document.querySelector('#view-connection .subscription-info');
        if (connectionSubInfo && data.profile && !data.rw_error) {
            const daysEl = document.getElementById('connection-remaining-days');
            const resultEl = document.getElementById('connection-result');

            const wasActive = !!daysEl;
            const expireAt = data.rw_user?.expireAt || data.rw_user?.expire_at;
            const expireMs = expireAt ? Date.parse(expireAt) : NaN;
            const remainingDays = Number.isNaN(expireMs)
                ? 0
                : Math.max(0, Math.floor((expireMs - Date.now()) / 86400000));
            const isActive = !!data.rw_user && remainingDays > 0;
            const needsRebuild = !resultEl && !!data.rw_user;

            if (wasActive !== isActive || needsRebuild) {
                // Redraw everything only if status changed or result block missing
                const username = document.getElementById('connection-username')?.textContent || `@${tg?.initDataUnsafe?.user?.username || SAFE_MOCK_USER_DATA?.username || 'user'}`;
                let connHtml = `
                    <div class="info-item connection-info-item">
                        <span class="material-symbols-rounded">person</span>
                        <div class="connection-info-label">
                            <span class="label">Пользователь</span>
                        </div>
                        <span class="value" id="connection-username">${escapeHtml(username)}</span>
                    </div>`;

                if (isActive) {
                    const hasWl = !!data.whitelist_user;
                    connHtml += `
                        <div class="info-item connection-info-item">
                            <span class="material-symbols-rounded">verified_user</span>
                            <div class="connection-info-label">
                                <span class="label">Статус</span>
                            </div>
                            <span class="value connection-status is-active">Активна</span>
                        </div>
                        <div class="info-item connection-info-item">
                            <span class="material-symbols-rounded">schedule</span>
                            <div class="connection-info-label">
                                <span class="label">Осталось времени</span>
                            </div>
                            <span class="value" id="connection-remaining-days">${remainingDays} дн.</span>
                        </div>`;

                    if (hasWl) {
                        const mainActive = window.selectedSubType !== 'whitelist';
                        connHtml += `
                        <div id="sub-type-switcher" class="sub-type-switcher">
                            <div class="sub-type-indicator${mainActive ? '' : ' whitelist'}"></div>
                            <button id="sub-type-main" class="sub-type-btn${mainActive ? ' active' : ''}" onclick="switchSubType('main')">
                                <span class="material-symbols-rounded" style="font-size: 16px; vertical-align: middle; margin-right: 4px;">verified_user</span>Основная
                            </button>
                            <button id="sub-type-whitelist" class="sub-type-btn${mainActive ? '' : ' active'}" onclick="switchSubType('whitelist')">
                                <span class="material-symbols-rounded" style="font-size: 16px; vertical-align: middle; margin-right: 4px;">shield_locked</span>Дополнительная
                            </button>
                        </div>`;
                    }

                    connHtml += `
                        <div id="conn-loading-placeholder" style="display:none; align-items:center; justify-content: space-between; gap:10px; margin-top:16px; padding: 14px 16px; background: rgba(255,255,255,0.04); border-radius: 16px;">
                            <div class="spinner" style="position: relative; width:20px; height:20px; border-width:2px; flex-shrink:0;"></div>
                            <span style="font-size:13px; opacity:0.6;">Получение данных...</span>
                        </div>
                        <div id="connection-result" class="connection-result" style="margin-top: 16px; padding: 16px; background: rgba(255,255,255,0.05); border-radius: 16px;">
                            <span style="font-size: 14px; color: var(--panel-icon); text-align: center;">Отсканируйте QR-код или скопируйте ссылку для настройки клиента</span>
                            <div id="conn-content" style="display: none; width: 100%; flex-direction: column; align-items: center; gap: 16px;">
                                <canvas id="qr-code-canvas" style="width: 160px; height: 160px; border-radius: 12px; background: white; padding: 8px; display: block;"></canvas>
                                <div style="display: flex; gap: 8px; width: 100%;">
                                    <button class="action-btn bounce" style="flex: 1; padding: 12px; font-size: 14px; background-color: rgba(255,255,255,0.1);" onclick="copySubLink()">
                                        <span class="material-symbols-rounded" style="font-size: 20px;">content_copy</span>
                                        Скопировать
                                    </button>
                                    <button class="action-btn bounce" style="flex: 1; padding: 12px; font-size: 14px; background-color: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary);" onclick="showInstructions()">
                                        <span class="material-symbols-rounded" style="font-size: 20px;">open_in_new</span>
                                        Подключить
                                    </button>
                                </div>
                            </div>
                        </div>`;
                } else {
                    connHtml += `
                        <div class="info-item connection-info-item">
                            <span class="material-symbols-rounded">verified_user</span>
                            <div class="connection-info-label">
                                <span class="label">Статус</span>
                            </div>
                            <span class="value connection-status is-expired">Истекла</span>
                        </div>
                        <div class="info-item connection-info-item">
                            <span class="material-symbols-rounded">schedule</span>
                            <div class="connection-info-label">
                                <span class="label">Осталось времени</span>
                            </div>
                            <span class="value connection-status is-expired no-dot">0 дней</span>
                        </div>
                        <div class="connection-expired-card">
                            <span class="material-symbols-rounded">event_busy</span>
                            <div>
                                <strong>Подписка истекла</strong>
                                <span>Продлите подписку, чтобы подключиться</span>
                            </div>
                        </div>`;
                }
                connectionSubInfo.innerHTML = connHtml;
                // Re-render QR code from cache if already fetched this session
                const cachedLink = subLinkCache[window.selectedSubType || 'main'];
                if (cachedLink) {
                    renderSubLink(cachedLink);
                    const resultDiv = document.getElementById('connection-result');
                    if (resultDiv) resultDiv.classList.add('animate-in');
                } else if (isActive) {
                    // Active sub with no cached link — auto-fetch on rebuild.
                    setTimeout(() => window.handleConnect && window.handleConnect(), 200);
                }
            }
        }

        // Update Tariff Cards (Owned status)
        if (data.profile && data.profile.tarif_name) {
            document.querySelectorAll('.tariff-card-v2').forEach(card => {
                const title = card.querySelector('h3').textContent;
                const btn = card.querySelector('.v2-buy-btn');
                if (btn) {
                    if (title === data.profile.tarif_name) {
                        btn.textContent = 'Уже активен';
                        btn.classList.add('owned');
                        btn.disabled = true;
                        btn.title = '';
                    } else if (data.profile.tariff_change_locked) {
                        btn.textContent = 'Недоступно';
                        btn.classList.add('owned');
                        btn.disabled = true;
                        btn.title = 'Ваш текущий тариф нельзя сменить';
                    } else {
                        btn.textContent = 'Купить';
                        btn.classList.remove('owned');
                        btn.disabled = false;
                        btn.title = '';
                    }
                }
            });
        }

        // Update Remaining Days (Sync secondary displays)
        if (data.rw_user) {
            const remDays = data.rw_user.remaining_days || 0;
            const subRemDaysDisplay = document.getElementById('sub-remaining-days-display');
            const connRemDaysDisplay = document.getElementById('connection-remaining-days');

            if (subRemDaysDisplay) subRemDaysDisplay.textContent = `Осталось дней: ${remDays}`;
            if (connRemDaysDisplay) connRemDaysDisplay.textContent = `${remDays} дней`;

            window.REMAINING_DAYS = remDays;
        }

        // Update Nodes (Server Status)
        const onlineCountEl = document.getElementById('online-count-display');
        const offlineCountEl = document.getElementById('offline-count-display');
        if (onlineCountEl && data.online_count !== undefined) onlineCountEl.textContent = `${data.online_count} онлайн`;
        if (offlineCountEl && data.offline_count !== undefined) offlineCountEl.textContent = `${data.offline_count} недоступно`;

        const nodesContainer = document.getElementById('nodes-list-container');
        if (nodesContainer && data.nodes) {
            // Only update nodes UI if we have data OR if the empty list is not an error
            if (data.nodes.length > 0 || !data.nodes_error) {
                let nodesHtml = '';
                data.nodes.forEach(node => {
                    let isOnline = node.isConnected;
                    let statusText = isOnline ? 'Доступно' : 'Недоступно';
                    let statusColor = isOnline ? '#4CAF50' : '#F44336';

                    if (node.use_manual_status) {
                        isOnline = node.manual_is_online;
                        statusText = node.custom_status || (isOnline ? 'Доступно' : 'Недоступно');
                        statusColor = isOnline ? '#4CAF50' : '#F44336';
                        if (node.custom_status) statusColor = '#BB86FC';
                    } else if (node.custom_status) {
                        statusText = node.custom_status;
                        statusColor = '#BB86FC';
                    }

                    const nodeJson = encodeURIComponent(JSON.stringify(node));

                    nodesHtml += `
                        <div class="server-selector bounce" style="margin-top: 10px;"
                             ${data.is_admin ? `onclick="handleSetNodeStatus('${escapeJsAttr(node.id)}', '${escapeJsAttr(nodeJson)}')"` : ''}>
                            <div class="server-info">
                                <div class="server-icon-wrapper">
                                    ${node.countryCode ? `
                                        <img src="${IS_DEBUG ? 'https://flagcdn.com/w80/' : '/tg-flags/w80/'}${escapeHtml(node.countryCode).toLowerCase()}.png" 
                                             class="flag-img" 
                                             alt="${escapeHtml(node.countryCode)}">
                                    ` : `
                                        <span class="material-symbols-rounded">
                                            ${node.isConnected ? 'lan' : 'lan_off'}
                                        </span>
                                    `}
                                </div>
                                <div class="server-details">
                                    <span class="server-name">${escapeHtml(node.display_name)}</span>
                                    <span class="server-ping">
                                        <span style="color: ${statusColor}; font-weight: 500;">${escapeHtml(statusText)}</span>
                                    </span>
                                </div>
                            </div>
                            ${data.is_admin ? '<span class="material-symbols-rounded" style="opacity: 0.3; font-size: 20px;">chevron_right</span>' : ''}
                        </div>`;
                });
                nodesContainer.innerHTML = nodesHtml;
            } else {
                console.warn('Sync nodes error or empty while error flag set, keeping previous list');
            }
        }

        // Update Devices
        const deviceCountEl = document.getElementById('devices-count-display');
        if (deviceCountEl && data.rw_user && !data.hwid_error) {
            deviceCountEl.innerHTML = `
                <span class="material-symbols-rounded" style="font-size: 14px;">devices</span>
                ${data.hwid_devices.length} / ${data.rw_user.hwidDeviceLimit || 0}
            `;
        }

        const devicesContainer = document.getElementById('devices-list-container');
        if (devicesContainer && data.hwid_devices && !data.hwid_error) {
            if (data.hwid_devices.length === 0) {
                devicesContainer.innerHTML = `
                    <div class="settings-empty">
                        <span class="material-symbols-rounded">devices_off</span>
                        <span>Нет подключённых устройств</span>
                    </div>`;
            } else {
                let devicesHtml = '';
                data.hwid_devices.forEach((device, index) => {
                    const idx = index + 1;
                    let icon = 'devices';
                    if (device.platform === 'Android') icon = 'smartphone';
                    else if (device.platform === 'Windows') icon = 'computer';
                    else if (device.platform === 'iOS') icon = 'phone_iphone';
                    else if (device.platform === 'macOS') icon = 'laptop_mac';
                    else if (device.platform === 'Linux') icon = 'terminal';

                    devicesHtml += `
                        <div class="device-row" id="device-row-${idx}">
                            <div class="device-row-icon">
                                <span class="material-symbols-rounded">${icon}</span>
                            </div>
                            <div class="device-row-info">
                                <span class="device-row-name">${escapeHtml(device.deviceModel) || "Неизвестное устройство"}</span>
                                <span class="device-row-meta">${escapeHtml(device.platform) || "—"} · ${escapeHtml(device.hwid.substring(0, 14))}...</span>
                            </div>
                            <button class="device-delete-btn bounce"
                                    onclick="handleDeleteDevice('${escapeJsAttr(device.hwid)}', ${idx})"
                                    title="Удалить устройство">
                                <span class="material-symbols-rounded">delete_outline</span>
                            </button>
                        </div>
                        ${index < data.hwid_devices.length - 1 ? '<div class="settings-divider"></div>' : ''}`;
                });
                devicesContainer.innerHTML = devicesHtml;
            }
        }

        // Update Slot Purchase Section
        const slotContainer = document.getElementById('slot-purchase-container');
        if (slotContainer && !data.rw_error) {
            if (data.rw_user) {
                slotContainer.innerHTML = `
                    <div class="settings-section">
                        <div class="settings-section-header">
                            <span class="settings-section-label">Слоты устройств</span>
                        </div>
                        <div class="settings-block">
                            <div class="slot-info-row">
                                <div class="slot-info-icon">
                                    <span class="material-symbols-rounded">add_circle</span>
                                </div>
                                <div class="slot-info-text">
                                    <span class="slot-info-title">Дополнительный слот</span>
                                    <span class="slot-info-sub">Подключите ещё одно устройство</span>
                                </div>
                                <button class="slot-buy-btn bounce" onclick="handleBuySlot()">
                                    100 ₽
                                </button>
                            </div>
                        </div>
                    </div>`;
            } else {
                slotContainer.innerHTML = '';
            }
        }

        // Background-prefetch subscription links once data is available.
        prefetchSubLinks();
    }

    // Referral system.
    // Данные прилетают вместе с sync-data (каждые 10 сек) и кэшируются,
    // поэтому открытие модалки мгновенное — без экрана «Загрузка…».
    // Отдельный referral-info-api оставлен как fallback на случай,
    // если кэш sync ещё пуст (первые секунды после запуска).
    window._referralLink = '';
    window._referralData = null;

    async function fetchReferralInfo() {
        const tg = window.Telegram?.WebApp;
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', CSRF_TOKEN);
        if (tg?.initData) formData.append('init_data', tg.initData);
        const resp = await fetch('/user/referral-info-api/', {
            method: 'POST',
            body: formData
        });
        const data = await resp.json();
        if (data.success && data.link) {
            window._referralLink = data.link;
            window._referralData = data;
            return data;
        }
        return null;
    }

    function renderReferralModal(data) {
        const reward = `${Number(data.reward || 100).toFixed(0)} ₽`;
        const earned = `${Number(data.earned || 0).toFixed(0)} ₽`;
        const customHtml = `
            <div style="width:100%;text-align:left;display:flex;flex-direction:column;gap:12px;">
                <div style="display:flex;gap:10px;">
                    <div style="flex:1;background:rgba(255,255,255,0.04);border-radius:14px;padding:10px 12px;text-align:center;">
                        <div style="font-size:11px;opacity:0.55;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px;">Приглашено</div>
                        <div style="font-size:20px;font-weight:600;">${data.invited}</div>
                    </div>
                    <div style="flex:1;background:rgba(76,175,80,0.08);border-radius:14px;padding:10px 12px;text-align:center;">
                        <div style="font-size:11px;opacity:0.55;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px;">Заработано</div>
                        <div style="font-size:20px;font-weight:600;color:#4CAF50;">${earned}</div>
                    </div>
                </div>
                <div style="display:flex;flex-direction:column;gap:8px;font-size:13px;opacity:0.75;">
                    <div style="display:flex;gap:10px;align-items:flex-start;">
                        <span class="material-symbols-rounded" style="color:var(--md-sys-color-primary);font-size:18px;flex-shrink:0;">share</span>
                        <span>Поделись своей ссылкой с другом</span>
                    </div>
                    <div style="display:flex;gap:10px;align-items:flex-start;">
                        <span class="material-symbols-rounded" style="color:var(--md-sys-color-primary);font-size:18px;flex-shrink:0;">shopping_bag</span>
                        <span>Друг покупает подписку</span>
                    </div>
                    <div style="display:flex;gap:10px;align-items:flex-start;">
                        <span class="material-symbols-rounded" style="color:#4CAF50;font-size:18px;flex-shrink:0;">payments</span>
                        <span>Ты получаешь <b>${reward}</b> на баланс автоматически</span>
                    </div>
                </div>
            </div>`;
        showModal({
            title: 'Реферальная система',
            message: `Приглашай друзей и получай ${reward} за каждого, кто купит подписку.`,
            icon: 'group_add',
            customHtml: customHtml,
            actionText: 'Скопировать',
            onAction: () => {
                // Инлайн-подтверждение в той же модалке (без второй
                // модалки «Ссылка скопирована»). false = не закрывать.
                copyReferralLink();
                return false;
            },
            closeBtnText: 'Закрыть'
        });
    }

    window.openReferralModal = () => {
        // Мгновенно из кэша sync-data — без «Загрузки…».
        if (window._referralData && window._referralData.link) {
            renderReferralModal(window._referralData);
            return;
        }
        // Fallback только если sync ещё не прилетел.
        showModal({
            title: 'Реферальная система',
            message: 'Загрузка…',
            icon: 'group_add',
            actionText: 'Закрыть',
            onAction: null,
            closeBtnText: 'Закрыть'
        });
        fetchReferralInfo().then((data) => {
            if (!data) {
                showModal({
                    title: 'Ошибка',
                    message: 'Не удалось загрузить реферальные данные.',
                    icon: 'error',
                    actionText: 'Ок',
                    onAction: hideModal
                });
                return;
            }
            renderReferralModal(data);
        }).catch(() => {
            showModal({
                title: 'Ошибка',
                message: 'Не удалось загрузить реферальные данные.',
                icon: 'error',
                actionText: 'Ок',
                onAction: hideModal
            });
        });
    };

    window.copyReferralLink = async () => {
        const link = window._referralLink || '';
        if (!link) return;
        const btn = document.getElementById('modal-action');
        const prevText = btn ? btn.textContent : '';
        const flashOk = () => {
            if (!btn) return;
            btn.textContent = 'Скопировано';
            btn.classList.add('copied');
            if (btn.animate) {
                btn.animate(
                    [{ transform: 'scale(0.96)' }, { transform: 'scale(1)' }],
                    { duration: 200, easing: 'ease-out' }
                );
            }
            setTimeout(() => {
                // Модалку могли уже закрыть — проверяем, что кнопка та же.
                if (document.getElementById('modal-action') === btn) {
                    btn.textContent = prevText || 'Скопировать';
                    btn.classList.remove('copied');
                }
            }, 1600);
        };
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(link);
            } else {
                const ta = document.createElement('textarea');
                ta.value = link;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                ta.remove();
            }
            if (window.Telegram?.WebApp?.HapticFeedback) {
                window.Telegram.WebApp.HapticFeedback.notificationOccurred(
                    'success'
                );
            }
            flashOk();
        } catch (e) {
            showModal({
                title: 'Ошибка',
                message: 'Не удалось скопировать ссылку.',
                icon: 'error',
                actionText: 'Ок',
                onAction: hideModal
            });
        }
    };

    async function bindReferralFromUrl() {
        try {
            const ref = new URLSearchParams(window.location.search).get('ref');
            if (!ref) return;
            if (sessionStorage.getItem('ref_bind_attempted_' + ref)) return;
            sessionStorage.setItem('ref_bind_attempted_' + ref, '1');
            const tg = window.Telegram?.WebApp;
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', CSRF_TOKEN);
            formData.append('ref_code', ref);
            if (tg?.initData) formData.append('init_data', tg.initData);
            const resp = await fetch('/user/bind-referral-api/', {
                method: 'POST',
                body: formData
            });
            await resp.json();
        } catch (e) {
            // silent — referral bind is best-effort
        }
    }

    // Lazy-load payment history
    window._historyLoaded = false;
    window._historyOffset = 0;
    window._lastBalance = null;

    function buildPaymentHtml(p) {
        const isTopup = p.order_type === 'TOPUP';
        const isReferral = p.order_type === 'REFERRAL';
        const isIncome = isTopup || isReferral;
        const isSlot = p.order_type === 'SLOT';
        let statusColor = '#EF5350';
        let statusText = 'Ошибка';
        if (p.status === 'PAID') {
            statusColor = '#4CAF50';
            statusText = 'Успешно';
        } else if (p.status === 'PENDING') {
            statusColor = '#FF9F0A';
            statusText = 'В обработке';
        }
        return `
            <div class="history-item" style="background: var(--panel-bg); border-radius: 20px; padding: 16px; display: flex; align-items: center; gap: 16px;">
                <div style="width: 44px; height: 44px; border-radius: 14px; background: ${isIncome ? 'rgba(76, 175, 80, 0.1)' : 'rgba(255, 255, 255, 0.05)'}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                    <span class="material-symbols-rounded" style="color: ${isIncome ? '#4CAF50' : '#FFFFFF'}; font-size: 24px; opacity: 0.8;">
                        ${isTopup ? 'account_balance_wallet' : (isReferral ? 'group_add' : 'shopping_bag')}
                    </span>
                </div>
                <div style="flex: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2px;">
                        <span style="font-weight: 500; font-size: 15px;">
                            ${isTopup ? 'Пополнение баланса' : (isReferral ? 'Реферальный бонус' : (isSlot ? 'Доп. слот' : (escapeHtml(p.tariff_name) || "Покупка тарифа")))}
                        </span>
                        <span style="font-weight: 600; font-size: 15px; color: ${isIncome ? '#4CAF50' : '#FFFFFF'};">
                            ${isIncome ? '+' : '-'}${p.amount.toFixed(0)} ₽
                        </span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; opacity: 0.5;">
                        <span>${p.created_at}</span>
                        <span style="color: ${statusColor}; opacity: 0.8;">
                            ${statusText}
                        </span>
                    </div>
                </div>
            </div>`;
    }

    async function fetchPayments(offset) {
        const tg = window.Telegram?.WebApp;
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', CSRF_TOKEN);
        formData.append('offset', offset);
        if (tg?.initData) formData.append('init_data', tg.initData);
        const resp = await fetch('/shop/payments-api/', { method: 'POST', body: formData });
        return await resp.json();
    }

    window.loadPaymentHistory = async (force) => {
        if (window._historyLoaded && !force) return;
        const container = document.getElementById('history-list-container');
        const loadMore = document.getElementById('history-load-more');
        if (!container) return;

        window._historyOffset = 0;
        container.innerHTML = `<div style="display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 40px 20px; opacity: 0.4; text-align: center;"><div class="spinner"></div><span>Загрузка...</span></div>`;

        try {
            const data = await fetchPayments(0);
            if (!data.success) throw new Error(data.error);

            if (data.payments.length === 0) {
                container.innerHTML = `
                    <div style="display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 40px 20px; opacity: 0.4; text-align: center;">
                        <span class="material-symbols-rounded" style="font-size: 48px;">receipt_long</span>
                        <span>История платежей пока пуста</span>
                    </div>`;
                if (loadMore) loadMore.style.display = 'none';
            } else {
                container.innerHTML = data.payments.map(buildPaymentHtml).join('');
                window._historyOffset = data.payments.length;
                if (loadMore) loadMore.style.display = data.has_more ? '' : 'none';
            }
            window._historyLoaded = true;
        } catch (e) {
            console.error('Failed to load payments', e);
            container.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 40px 20px; opacity: 0.4; text-align: center;">
                    <span class="material-symbols-rounded" style="font-size: 48px;">error</span>
                    <span>Ошибка загрузки истории</span>
                </div>`;
        }
    };

    window.loadMorePayments = async () => {
        const container = document.getElementById('history-list-container');
        const loadMore = document.getElementById('history-load-more');
        if (!container) return;

        try {
            const data = await fetchPayments(window._historyOffset);
            if (!data.success) throw new Error(data.error);

            container.insertAdjacentHTML('beforeend', data.payments.map(buildPaymentHtml).join(''));
            window._historyOffset += data.payments.length;
            if (loadMore) loadMore.style.display = data.has_more ? '' : 'none';
        } catch (e) {
            console.error('Failed to load more payments', e);
        }
    };

    // ---- Admin Billing Panel ----
    window._billingDays = 30;
    window._billingRange = null;
    window._billingData = null;

    function billingFormData(extra) {
        const tg = window.Telegram?.WebApp;
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', CSRF_TOKEN);
        if (tg?.initData) formData.append('init_data', tg.initData);
        if (extra) {
            Object.keys(extra).forEach(k => formData.append(k, extra[k]));
        }
        return formData;
    }

    function billingHaptic(kind) {
        try {
            const h = window.Telegram?.WebApp?.HapticFeedback;
            if (!h) return;
            if (kind === 'success') h.notificationOccurred('success');
            else h.impactOccurred('light');
        } catch (e) {}
    }

    window.openBilling = () => {
        billingHaptic();
        window._billingPayersPage = 1;
        activateTabById('view-billing', 'Билинг');
        fetchBilling();
    };

    // Перезагрузка только доходов и графика — остальная страница не мигает.
    function billingReloadStats(params) {
        const sec = document.querySelector('.billing-sec-income');
        if (!sec) {
            fetchBilling();
            return;
        }
        sec.classList.add('billing-updating');
        fetch('/shop/billing-api/', {
            method: 'POST',
            body: billingFormData(params)
        })
            .then(resp => resp.json())
            .then(d => {
                if (!d.success) throw new Error(d.error);
                if (window._billingData) window._billingData.stats = d.stats;
                else window._billingData = d;
                sec.innerHTML = billingIncomeHtml(window._billingData);
                renderBillingChart(window._billingData);
            })
            .catch(e => console.error('Billing stats refresh failed', e))
            .finally(() => sec.classList.remove('billing-updating'));
    }

    window.setBillingDays = (days) => {
        days = Number(days) || 30;
        window._billingDays = days;
        window._billingRange = null;
        billingHaptic();
        billingReloadStats({ days });
    };

    window.setBillingRange = (from, to) => {
        window._billingRange = { from, to };
        billingHaptic();
        billingReloadStats({ date_from: from, date_to: to });
    };

    window.billingRangeModal = () => {
        const today = new Date().toISOString().slice(0, 10);
        const r = window._billingRange || {};
        const customHtml = `
            <div style="display: flex; flex-direction: column; gap: 10px; width: 100%; text-align: left;">
                <label style="font-size: 12px; opacity: 0.6;">С
                    <input id="billing-range-from" class="modal-input" style="text-align: left; margin-top: 4px;" type="date" max="${today}" value="${r.from || ''}">
                </label>
                <label style="font-size: 12px; opacity: 0.6;">По (можно в будущее — видно предстоящие списания)
                    <input id="billing-range-to" class="modal-input" style="text-align: left; margin-top: 4px;" type="date" value="${r.to || ''}">
                </label>
            </div>`;
        showModal({
            title: 'Диапазон доходов',
            message: '',
            icon: 'date_range',
            customHtml: customHtml,
            actionText: 'Показать',
            onAction: billingApplyRange,
            closeBtnText: 'Отмена'
        });
    };

    window.billingApplyRange = () => {
        const from = (document.getElementById('billing-range-from') || {}).value || '';
        const to = (document.getElementById('billing-range-to') || {}).value || '';
        if (!from || !to || from > to) {
            showModal({ title: 'Ошибка', message: 'Проверьте даты: «с» должна быть не позже «по».', icon: 'error', actionText: 'Ок', onAction: hideModal });
            return;
        }
        setBillingRange(from, to);
    };

    async function fetchBilling() {
        const container = document.getElementById('billing-content');
        if (!container) return;
        container.innerHTML = `<div style="display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 40px 20px; opacity: 0.4; text-align: center;"><div class="spinner"></div></div>`;
        try {
            const range = window._billingRange;
            const params = range
                ? { date_from: range.from, date_to: range.to }
                : { days: window._billingDays };
            const resp = await fetch('/shop/billing-api/', {
                method: 'POST',
                body: billingFormData(params)
            });
            const data = await resp.json();
            if (!data.success) throw new Error(data.error || 'forbidden');
            window._billingData = data;
            renderBilling(data);
        } catch (e) {
            console.error('Billing load failed', e);
            container.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 40px 20px; opacity: 0.4; text-align: center;">
                    <span class="material-symbols-rounded" style="font-size: 48px;">error</span>
                    <span>Нет доступа или ошибка загрузки</span>
                </div>`;
        }
    }

    function fmtRub(n) {
        return `${Number(n || 0).toFixed(0)} ₽`;
    }

    // ---- Интерактивный график: линии/столбцы, тултип, легенда ----
    window._billingChartMode = 'lines';
    window._billingHidden = { profit: false, turnover: false, refund: false, servers: false, ledger: false, wallet: false };

    window.billingToggleSeries = (key) => {
        window._billingHidden[key] = !window._billingHidden[key];
        const data = window._billingData;
        if (data) renderBillingChart(data);
    };

    window.billingChartMode = (mode) => {
        window._billingChartMode = mode;
        const data = window._billingData;
        if (data) renderBillingChart(data);
    };

    function billingFmtDate(iso) {
        const d = new Date(iso + 'T00:00:00');
        return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}`;
    }

    function billingFmtDateLong(iso) {
        if (!iso) return '';
        const months = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
        const d = new Date(iso + 'T00:00:00');
        if (isNaN(d)) return iso;
        return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
    }

    function billingSeries(timeline) {
        return [
            { key: 'profit', label: 'Прибыль', color: '#8B7CF6', get: (p) => p.total || 0 },
            { key: 'turnover', label: 'Оборот', color: '#4C8DFF', get: (p) => p.gross || 0 },
            { key: 'refund', label: 'Возвраты', color: '#FF9F0A', get: (p) => p.refund || 0 },
            { key: 'servers', label: 'Серверы', color: '#EF5350', get: (p) => p.servers || 0 },
            { key: 'ledger', label: 'Внеплановые', color: '#4CAF50', get: (p) => p.ledger || 0 },
            { key: 'wallet', label: 'Кошелёк', color: '#2DD4BF', dashed: true, get: (p) => p.wallet || 0 },
        ];
    }

    function renderBillingChart(data) {
        const host = document.getElementById('billing-chart-host');
        if (!host) return;
        const stats = data.stats || {};
        const period = stats.period || { net: 0, gross: 0 };
        const timeline = stats.timeline || [];
        const hidden = window._billingHidden;
        const mode = window._billingChartMode;
        const series = billingSeries(timeline);
        const serversTotal = timeline.reduce((sum, p) => sum + (Number(p.servers) || 0), 0);
        const ledgerTotal = timeline.reduce((sum, p) => sum + (Number(p.ledger) || 0), 0);

        const legend = (key, label, color, value) => `
            <button class="bounce billing-legend ${hidden[key] ? 'off' : ''}" onclick="billingToggleSeries('${key}')" style="flex: 1 1 40%; min-width: 0; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.07); border-radius: 14px; padding: 10px 12px; text-align: left; color: #fff;">
                <div style="font-size: 16px; font-weight: 700;">${fmtRub(value)}</div>
                <div style="display: flex; align-items: center; gap: 6px; font-size: 12px; opacity: 0.75; margin-top: 2px;">
                    <span style="width: 8px; height: 8px; border-radius: 50%; background: ${color}; flex-shrink: 0;"></span>${label}
                </div>
            </button>`;

        host.innerHTML = `
            <div class="billing-legend-row" style="display: flex; gap: 10px; flex-wrap: wrap;">
                ${legend('profit', 'Прибыль', '#8B7CF6', period.net)}
                ${legend('turnover', 'Оборот', '#4C8DFF', period.gross)}
                ${legend('refund', 'Возвраты', '#FF9F0A', period.refunds || 0)}
                ${legend('servers', 'Серверы', '#EF5350', serversTotal)}
                ${legend('ledger', 'Внеплановые', '#4CAF50', ledgerTotal)}
                ${legend('wallet', 'Кошелёк', '#2DD4BF', (stats.yoomoney && stats.yoomoney.total) || 0)}
            </div>
            <div id="billing-chart-wrap" style="position: relative; margin-top: 4px;">
                ${billingChartSvg(timeline, series, hidden, mode)}
                <div id="billing-chart-tip" class="billing-chart-tip" style="display: none;"></div>
            </div>
            <div style="display: flex; gap: 8px; justify-content: flex-end;">
                <button class="bounce billing-mode-btn ${mode === 'lines' ? 'on' : ''}" onclick="billingChartMode('lines')">
                    <span class="material-symbols-rounded" style="font-size: 16px;">show_chart</span>Линии
                </button>
                <button class="bounce billing-mode-btn ${mode === 'bars' ? 'on' : ''}" onclick="billingChartMode('bars')">
                    <span class="material-symbols-rounded" style="font-size: 16px;">bar_chart</span>Столбцы
                </button>
            </div>`;
        bindBillingChart(timeline, series, hidden, mode);
    }

    function billingChartSvg(timeline, series, hidden, mode) {
        const W = 320, H = 132, PADL = 34, PADR = 8, PADT = 8, PADB = 20;
        const vis = series.filter(s => !hidden[s.key]);
        const all = timeline.flatMap(p => vis.map(s => s.get(p)));
        // Шкала умеет минусы (внеплановые расходы): низ — минимум,
        // верх — максимум +15%. Без минусов как раньше: [0, max * 1.15].
        const rawLo = all.length ? Math.min(0, ...all) : 0;
        const rawHi = all.length ? Math.max(0, ...all) : 0;
        const span = (rawHi - rawLo) || 1;
        const lo = rawLo < 0 ? rawLo - span * 0.05 : 0;
        const hi = rawHi + span * 0.15;
        const n = timeline.length;
        const stepX = n > 1 ? (W - PADL - PADR) / (n - 1) : 0;
        const x = (i) => PADL + i * stepX;
        const y = (v) => PADT + ((hi - v) / (hi - lo)) * (H - PADT - PADB);
        const zeroY = y(0);

        const fmtTick = (v) => Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${Math.round(v)}`;
        let grid = '';
        for (let g = 0; g <= 3; g++) {
            const gy = PADT + ((H - PADT - PADB) * g) / 3;
            const gv = hi - ((hi - lo) * g) / 3;
            grid += `<line x1="${PADL}" y1="${gy}" x2="${W - PADR}" y2="${gy}" stroke="rgba(255,255,255,0.07)"/>`
                + `<text x="${PADL - 4}" y="${gy + 3}" font-size="8" fill="rgba(255,255,255,0.4)" text-anchor="end">${fmtTick(gv)}</text>`;
        }
        // Ноль подчёркиваем ярче, когда есть минусы.
        const zeroLine = rawLo < 0
            ? `<line x1="${PADL}" y1="${zeroY.toFixed(1)}" x2="${W - PADR}" y2="${zeroY.toFixed(1)}" stroke="rgba(255,255,255,0.22)"/>`
            : '';

        const idx = [];
        const count = Math.min(7, n);
        for (let k = 0; k < count; k++) {
            idx.push(Math.round((k * (n - 1)) / Math.max(1, count - 1)));
        }
        const labels = [...new Set(idx)].map(i =>
            `<text x="${x(i)}" y="${H - 6}" font-size="8" fill="rgba(255,255,255,0.4)" text-anchor="middle">${billingFmtDate(timeline[i].date)}</text>`
        ).join('');

        const fmtAxis = (v) => Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${Math.round(v)}`;
        let body = '';
        if (mode === 'bars') {
            // Столбец = сумма всех видимых серий от нулевой линии;
            // цвет — по доминирующей (по модулю), как в легенде.
            const barGrad = { profit: 'billing-bar-purple', turnover: 'billing-bar-blue', refund: 'billing-bar-orange', servers: 'billing-bar-red', ledger: 'billing-bar-green', wallet: 'billing-bar-teal' };
            const bw = Math.max(3, Math.min(26, stepX * 0.7));
            body = timeline.map((p, i) => {
                const v = vis.reduce((s, sv) => s + sv.get(p), 0);
                const yv = y(v);
                const top = Math.min(zeroY, yv);
                let h = Math.abs(yv - zeroY);
                if (v !== 0) h = Math.max(3, h);
                const bx = x(i) - bw / 2;
                let dom = 'profit';
                let best = -1;
                vis.forEach(sv => {
                    const svv = Math.abs(sv.get(p));
                    if (svv > best) {
                        best = svv;
                        dom = sv.key;
                    }
                });
                const ty = v >= 0 ? top - 4 : top + h + 10;
                const tag = v !== 0
                    ? `<text x="${x(i).toFixed(1)}" y="${ty.toFixed(1)}" font-size="8" font-weight="600" fill="rgba(255,255,255,0.75)" text-anchor="middle">${fmtAxis(v)}</text>`
                    : '';
                return `<rect x="${bx.toFixed(1)}" y="${top.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="3" fill="url(#${barGrad[dom] || 'billing-bar-purple'})"/>${tag}`;
            }).join('');
        } else {
            body = vis.map(s => {
                const d = timeline.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(s.get(p)).toFixed(1)}`).join(' ');
                const dash = s.dashed ? ' stroke-dasharray="5,4"' : '';
                const draw = s.dashed ? '' : ' class="billing-draw"';
                return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linecap="round"${dash} pathLength="1"${draw}/>`
                    + timeline.map((p, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(s.get(p)).toFixed(1)}" r="${n > 45 ? 0 : 2}" fill="${s.color}"/>`).join('');
            }).join('');
            const areaS = vis.find(s => s.key === 'profit');
            if (areaS && n > 1) {
                const d = timeline.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(areaS.get(p)).toFixed(1)}`).join(' ');
                body += `<path d="${d} L${x(n - 1).toFixed(1)},${zeroY.toFixed(1)} L${x(0).toFixed(1)},${zeroY.toFixed(1)} Z" fill="url(#billing-area)" opacity="0.5"/>`;
            }
        }

        // Маркер «сегодня»: когда график продлён в будущее (предстоящие
        // списания за сервера), пунктиром отделяем прошлое от прогноза.
        const todayIso = new Date().toISOString().slice(0, 10);
        const todayIdx = timeline.findIndex(p => p.date === todayIso);
        let todayMark = '';
        if (todayIdx >= 0 && timeline[n - 1].date > todayIso) {
            const tx = x(todayIdx);
            todayMark = `<line x1="${tx.toFixed(1)}" y1="${PADT}" x2="${tx.toFixed(1)}" y2="${H - PADB}" stroke="rgba(255,255,255,0.3)" stroke-dasharray="2,3"/>`
                + `<text x="${(tx + 4).toFixed(1)}" y="${PADT + 8}" font-size="8" fill="rgba(255,255,255,0.5)">сегодня</text>`;
        }

        return `
            <svg id="billing-chart-svg" viewBox="0 0 ${W} ${H}" style="width: 100%; display: block; touch-action: pan-y;">
                <defs>
                    <linearGradient id="billing-area" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#8B7CF6" stop-opacity="0.4"/>
                        <stop offset="1" stop-color="#8B7CF6" stop-opacity="0.02"/>
                    </linearGradient>
                    <linearGradient id="billing-bar" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#A78BFA" stop-opacity="0.95"/>
                        <stop offset="1" stop-color="#7C6CF0" stop-opacity="0.55"/>
                    </linearGradient>
                    <linearGradient id="billing-bar-purple" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#A78BFA" stop-opacity="0.95"/>
                        <stop offset="1" stop-color="#7C6CF0" stop-opacity="0.55"/>
                    </linearGradient>
                    <linearGradient id="billing-bar-blue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#6FA8FF" stop-opacity="0.95"/>
                        <stop offset="1" stop-color="#3B78E0" stop-opacity="0.55"/>
                    </linearGradient>
                    <linearGradient id="billing-bar-orange" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#FFB84D" stop-opacity="0.95"/>
                        <stop offset="1" stop-color="#E08A1E" stop-opacity="0.55"/>
                    </linearGradient>
                    <linearGradient id="billing-bar-red" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#FF8A80" stop-opacity="0.95"/>
                        <stop offset="1" stop-color="#D32F2F" stop-opacity="0.55"/>
                    </linearGradient>
                    <linearGradient id="billing-bar-green" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#81C784" stop-opacity="0.95"/>
                        <stop offset="1" stop-color="#388E3C" stop-opacity="0.55"/>
                    </linearGradient>
                    <linearGradient id="billing-bar-teal" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stop-color="#5EEAD4" stop-opacity="0.95"/>
                        <stop offset="1" stop-color="#14B8A6" stop-opacity="0.55"/>
                    </linearGradient>
                    <clipPath id="billing-clip">
                        <rect x="${PADL}" y="${PADT}" width="${W - PADL - PADR}" height="${H - PADT - PADB}" rx="4"/>
                    </clipPath>
                </defs>
                ${grid}
                <g clip-path="url(#billing-clip)">${body}</g>
                ${zeroLine}
                ${labels}
                ${todayMark}
                <line id="billing-cross" y1="${PADT}" y2="${H - PADB}" stroke="rgba(255,255,255,0.35)" stroke-dasharray="3,3" style="display: none;"/>
                <rect id="billing-hit" x="${PADL}" y="${PADT}" width="${W - PADL - PADR}" height="${H - PADT - PADB}" fill="transparent"/>
            </svg>`;
    }

    function bindBillingChart(timeline, series, hidden, mode) {
        const svg = document.getElementById('billing-chart-svg');
        const hit = document.getElementById('billing-hit');
        const cross = document.getElementById('billing-cross');
        const tip = document.getElementById('billing-chart-tip');
        const wrap = document.getElementById('billing-chart-wrap');
        if (!svg || !hit || !tip || !wrap || !timeline.length) return;
        const W = 320, PADL = 34, PADR = 8;
        const n = timeline.length;
        const stepX = n > 1 ? (W - PADL - PADR) / (n - 1) : 0;

        const showAt = (clientX) => {
            const rect = svg.getBoundingClientRect();
            const scale = W / rect.width;
            const sx = (clientX - rect.left) * scale;
            let i = Math.round((sx - PADL) / (stepX || 1));
            i = Math.max(0, Math.min(n - 1, i));
            const p = timeline[i];
            const cx = PADL + i * stepX;
            cross.setAttribute('x1', cx);
            cross.setAttribute('x2', cx);
            cross.style.display = '';
            const rows = series.filter(s => !hidden[s.key]).map(s =>
                `<div style="display: flex; align-items: center; gap: 6px; font-size: 12px; margin-top: 2px;">
                    <span style="width: 8px; height: 8px; border-radius: 50%; background: ${s.color};"></span>
                    <span style="opacity: 0.7;">${s.label}</span>
                    <b style="margin-left: auto;">${fmtRub(s.get(p))}</b>
                </div>`
            ).join('');
            tip.innerHTML = `<div style="font-size: 11px; opacity: 0.6;">${billingFmtDate(p.date)}</div>${rows}`;
            tip.style.display = 'block';
            const tipX = Math.min(Math.max(cx / scale + 12, 4), Math.max(4, rect.width - 148));
            tip.style.left = `${tipX}px`;
            tip.style.top = '0px';
        };
        const hide = () => {
            cross.style.display = 'none';
            tip.style.display = 'none';
        };
        hit.addEventListener('mousemove', (e) => showAt(e.clientX));
        hit.addEventListener('mouseleave', hide);
        hit.addEventListener('touchstart', (e) => {
            if (e.touches[0]) showAt(e.touches[0].clientX);
        }, { passive: true });
        hit.addEventListener('touchmove', (e) => {
            if (e.touches[0]) showAt(e.touches[0].clientX);
        }, { passive: true });
        hit.addEventListener('touchend', hide);
    }

    window.openPayerChat = (telegramId, username) => {
        billingHaptic();
        const url = username
            ? `https://t.me/${username}`
            : `tg://user?id=${telegramId}`;
        try {
            const tg = window.Telegram?.WebApp;
            if (tg && tg.openTelegramLink) {
                tg.openTelegramLink(url);
                return;
            }
        } catch (e) {}
        window.open(url, '_blank');
    };

    window.billingAvatarFallback = (img) => {
        const el = img.parentElement;
        const initial = (el && el.dataset && el.dataset.initial) || 'U';
        if (el) el.innerHTML = `<span style="font-size: 18px; font-weight: 600;">${escapeHtml(initial)}</span>`;
    };

    function billingIncomeHtml(data) {
        const stats = data.stats || {};
        const period = stats.period || { channels: {}, gross: 0, net: 0, count: 0 };
        const ch = period.channels || {};
        const card = ch.card || { gross: 0, net: 0, count: 0 };
        const sbp = ch.sbp || { gross: 0, net: 0, count: 0 };
        const crypto = ch.crypto || { gross: 0, net: 0, count: 0 };
        const other = ch.platega_other || { gross: 0, net: 0, count: 0 };
        const days = stats.days || 30;
        const range = window._billingRange;
        const pillStyle = (on) => `flex: 1; border: ${on ? '1px solid var(--md-sys-color-primary)' : '1px solid rgba(255,255,255,0.1)'}; background: ${on ? 'rgba(208,188,255,0.12)' : 'rgba(255,255,255,0.04)'}; color: #fff; border-radius: 12px; padding: 8px; font-size: 13px;`;
        const pills = [7, 30, 90].map(d => `
            <button class="bounce" data-days="${d}" onclick="setBillingDays(${d})" style="${pillStyle(!range && d === days)}">${d} дн.</button>
        `).join('') + `
            <button class="bounce" onclick="billingRangeModal()" title="Свой диапазон" style="${pillStyle(!!range)} display: flex; align-items: center; justify-content: center; gap: 4px; white-space: nowrap;">
                <span class="material-symbols-rounded" style="font-size: 16px;">date_range</span>${range ? `${billingFmtDate(range.from)}–${billingFmtDate(range.to)}` : ''}
            </button>`;
        const profit = Number(period.profit ?? period.net);
        return `
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="font-size: 12px; opacity: 0.55; text-transform: uppercase; letter-spacing: 0.5px;">Доходы · чистыми</div>
                    <div style="font-size: 20px; font-weight: 700; color: #4CAF50;">${fmtRub(period.net)}</div>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="font-size: 12px; opacity: 0.55;">Прибыль с расходами</div>
                    <div style="font-size: 16px; font-weight: 700; color: ${profit >= 0 ? '#4CAF50' : '#EF5350'};">${fmtRub(profit)}</div>
                </div>
                <div id="billing-period-pills" style="display: flex; gap: 8px;">${pills}</div>
                <div class="billing-channels">
                    <div class="billing-channel" style="background: rgba(208,188,255,0.07);">
                        <div class="billing-channel-head"><span class="material-symbols-rounded">credit_card</span>Карты · −3%</div>
                        <div class="billing-channel-sum">${fmtRub(card.net)}</div>
                        <div class="billing-channel-sub">${card.count} пл. · ${fmtRub(card.gross)}</div>
                    </div>
                    <div class="billing-channel" style="background: rgba(76,175,80,0.08);">
                        <div class="billing-channel-head"><span class="material-symbols-rounded">bolt</span>СБП · −4%</div>
                        <div class="billing-channel-sum">${fmtRub(sbp.net)}</div>
                        <div class="billing-channel-sub">${sbp.count} пл. · ${fmtRub(sbp.gross)}</div>
                    </div>
                    <div class="billing-channel" style="background: rgba(255,159,10,0.08);">
                        <div class="billing-channel-head"><span class="material-symbols-rounded">savings</span>Крипто · −4%</div>
                        <div class="billing-channel-sum">${fmtRub(crypto.net)}</div>
                        <div class="billing-channel-sub">${crypto.count} пл. · ${fmtRub(crypto.gross)}</div>
                    </div>
                </div>
                ${other.count ? `<div style="font-size: 12px; opacity: 0.5; text-align: center;">Platega без метода (стар.): ${fmtRub(other.net)} · ${other.count} пл.</div>` : ''}
                <div id="billing-chart-host" style="display: flex; flex-direction: column; gap: 10px;"></div>
                <div style="font-size: 12px; opacity: 0.5; text-align: center;">Всего платежей: ${period.count} · брутто ${fmtRub(period.gross)}</div>`;
    }

    function renderBilling(data) {
        const container = document.getElementById('billing-content');
        if (!container) return;
        const stats = data.stats || {};

        const balances = Array.isArray(data.balances) ? data.balances : [];
        const rub = balances.find(b => (b.currency || '').toUpperCase() === 'RUB');
        const usdt = balances.find(b => (b.currency || '').toUpperCase() === 'USDT');
        const yo = (data.stats && data.stats.yoomoney) || {};
        const yoBalance = (yo.error || yo.balance == null) ? null : Number(yo.balance);
        // Доступно = USDT доступно (amount минус «в процессе») × курс + кошелёк.
        // RUB-баланс — деньги НА холде, в итог не входит.
        // Бэкенд присылает готовый разбор (usdt_available/_in_process),
        // для старых ответов — fallback на amount − frozenBalance.
        const usdRate = Number(data.usd_rub_rate || 0);
        const usdtTotal = usdt ? Number(usdt.amount || 0) : 0;
        const usdtFrozen = usdt ? Number(usdt.frozenBalance || usdt.frozen || usdt.pending || 0) : 0;
        const usdtAvail = (data.usdt_available != null) ? Number(data.usdt_available || 0) : Math.max(0, usdtTotal - usdtFrozen);
        const usdtProcess = (data.usdt_in_process != null) ? Number(data.usdt_in_process || 0) : Math.max(0, usdtTotal - usdtAvail);
        const usdtRub = Math.floor(usdtAvail * usdRate);
        const combinedTotal = usdtRub + (yoBalance || 0);
        const rubFrozen = rub ? Number(rub.frozenBalance || 0) : 0;
        const yoRow = `
            ${yo.error
                ? `<div style="font-size: 12px; opacity: 0.55; text-align: center; background: rgba(255,255,255,0.04); border-radius: 14px; padding: 12px;">Кошелёк ЮMoney недоступен</div>`
                : `<div style="display: flex; align-items: center; gap: 10px; background: rgba(208,188,255,0.07); border-radius: 14px; padding: 12px;">
                    <span class="material-symbols-rounded" style="font-size: 20px; color: var(--md-sys-color-primary);">account_balance</span>
                    <div style="flex: 1; min-width: 0;">
                        <div style="font-size: 14px; font-weight: 600;">ЮMoney · ${escapeHtml(yo.account_masked || '')}</div>
                        <div style="font-size: 11px; opacity: 0.55;">кошелёк</div>
                    </div>
                    <div style="font-size: 17px; font-weight: 700; white-space: nowrap;">${fmtRub(yoBalance)}</div>
                </div>`}
            <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(76,175,80,0.08); border-radius: 14px; padding: 12px;">
                <div style="font-size: 12px; opacity: 0.65; text-transform: uppercase; letter-spacing: 0.5px;">Итого доступно</div>
                <div style="font-size: 19px; font-weight: 700; color: #4CAF50;">${fmtRub(combinedTotal)}</div>
            </div>`;
        const balanceCard = (title, avail, availLabel, hold, holdNote, subLine) => `
            <div style="flex: 1; min-width: 0; background: rgba(255,255,255,0.04); border-radius: 14px; padding: 12px; text-align: center;">
                <div style="display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 11px; opacity: 0.55; text-transform: uppercase; letter-spacing: 0.5px;">
                    <span class="material-symbols-rounded" style="font-size: 15px;">account_balance_wallet</span>${title}
                </div>
                <div style="font-size: 19px; font-weight: 700; margin-top: 2px;">${avail}</div>
                <div style="font-size: 11px; opacity: 0.55; margin-top: 2px;">${availLabel}</div>
                ${subLine ? `<div style="font-size: 11px; opacity: 0.45; margin-top: 2px;">${subLine}</div>` : ''}
                ${hold == null ? '' : `<div style="display: flex; align-items: center; justify-content: center; gap: 4px; font-size: 11px; opacity: 0.55; margin-top: 4px;">
                    <span class="material-symbols-rounded" style="font-size: 13px;">hourglass_top</span>${holdNote === 'в процессе выплаты' ? 'В процессе' : 'Холд'}: ${hold}
                </div>`}
                ${holdNote && holdNote !== 'в процессе выплаты' ? `<div style="font-size: 10px; opacity: 0.4;">${holdNote}</div>` : ''}
            </div>`;
        const balancesHtml = data.balances_error
            ? `<div style="font-size: 13px; opacity: 0.6;">Балансы Platega недоступны</div>`
            : `
            <div class="billing-balances" style="display: flex; gap: 10px;">
                ${balanceCard('Platega RUB', rub ? fmtRub(rub.amount) : '—', 'На холде', rubFrozen > 0 ? fmtRub(rubFrozen) : null, rubFrozen > 0 ? 'холд 3 дня' : '')}
                ${balanceCard('Platega USDT', usdt ? Number(usdtAvail).toFixed(2) : '—', 'Доступно', usdtProcess > 0 ? Number(usdtProcess).toFixed(2) + ' USDT' : null, usdtProcess > 0 ? 'в процессе выплаты' : '', usdt ? `≈ ${fmtRub(usdtRub)}` : '')}
            </div>
            ${yoRow}`;

        const servers = (data.servers && data.servers.servers) || [];
        const serversHtml = servers.length ? servers.map(s => `
            <div class="billing-server-row" style="background: rgba(255,255,255,0.04);">
                <div style="flex: 1; min-width: 0;">
                    <div style="font-size: 14px; font-weight: 500;">${escapeHtml(s.name)}</div>
                    <div style="font-size: 12px; opacity: 0.55;">${fmtRub(s.monthly_cost)} · до ${s.pay_day} числа</div>
                    <div style="display: flex; align-items: center; gap: 4px; font-size: 12px; margin-top: 2px; color: ${(s.paid_this_month || s.auto_paid) ? '#4CAF50' : (s.overdue ? '#EF5350' : 'rgba(255,255,255,0.55)')};">
                        <span class="material-symbols-rounded" style="font-size: 15px;">${s.paid_this_month ? 'check_circle' : (s.auto_paid ? 'autorenew' : (s.overdue ? 'warning' : 'schedule'))}</span>
                        ${s.paid_this_month ? 'Оплачен в этом месяце' : (s.auto_paid ? 'Оплачен автоматически' : (s.overdue ? 'Просрочен' : (s.last_paid ? `Оплачен: ${s.last_paid}` : 'Ещё не оплачивался')))}
                    </div>
                </div>
                <div class="billing-server-actions">
                    ${(s.paid_this_month || s.auto_paid) ? '' : `<button class="action-btn bounce" onclick="billingServerPaid(${s.id})" title="Отметить оплаченным" style="background: rgba(76,175,80,0.15); color: #4CAF50; border-radius: 12px; padding: 8px 12px; font-size: 13px; white-space: nowrap;">Оплачен</button>`}
                    <button class="action-btn bounce" onclick="billingServerModal(${s.id})" title="Изменить" style="background: rgba(255,255,255,0.06); border-radius: 12px; padding: 8px; color: #fff;"><span class="material-symbols-rounded" style="font-size: 18px;">edit</span></button>
                    <button class="action-btn bounce" onclick="billingServerDelete(${s.id})" title="Удалить" style="background: rgba(239,83,80,0.12); border-radius: 12px; padding: 8px; color: #EF5350;"><span class="material-symbols-rounded" style="font-size: 18px;">delete</span></button>
                </div>
            </div>
        `).join('') : `<div style="font-size: 13px; opacity: 0.55; text-align: center; padding: 8px;">Сервера не добавлены</div>`;

        const ledger = (data.ledger && data.ledger.entries) || [];
        const ledgerTotal = data.ledger ? Number(data.ledger.total || 0) : 0;
        const ledgerHtml = ledger.length ? ledger.map(e => {
            const positive = Number(e.amount) >= 0;
            return `
            <div class="billing-server-row" style="background: rgba(255,255,255,0.04);">
                <span class="material-symbols-rounded" style="font-size: 20px; color: ${positive ? '#4CAF50' : '#EF5350'}; flex-shrink: 0;">${positive ? 'trending_up' : 'trending_down'}</span>
                <div style="flex: 1; min-width: 0;">
                    <div style="font-size: 14px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(e.name)}</div>
                    <div style="font-size: 12px; opacity: 0.55; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(billingFmtDateLong(e.entry_date))}</div>
                </div>
                <div style="font-size: 15px; font-weight: 700; color: ${positive ? '#4CAF50' : '#EF5350'}; white-space: nowrap; flex-shrink: 0;">${positive ? '+' : ''}${fmtRub(e.amount)}</div>
                <button class="action-btn bounce" onclick="billingLedgerDelete(${e.id})" title="Удалить" style="flex: 0 0 auto; width: auto; background: rgba(239,83,80,0.12); border-radius: 12px; padding: 8px; color: #EF5350;"><span class="material-symbols-rounded" style="font-size: 18px;">delete</span></button>
            </div>`;
        }).join('') : `<div style="font-size: 13px; opacity: 0.55; text-align: center; padding: 4px;">Нет записей за месяц</div>`;

        window._billingPayers = (stats && stats.top_payers) || [];
        if (!window._billingPayersQuery) window._billingPayersQuery = '';
        if (!window._billingPayersPage) window._billingPayersPage = 1;
        const payersHtml = `<input id="billing-payer-search" class="modal-input" style="text-align: left;" placeholder="Поиск по имени или ID…" value="${escapeHtml(window._billingPayersQuery)}" oninput="billingPayerSearch(this.value)">
            <div id="billing-payer-rows"></div>
            <div id="billing-payer-hidden"></div>`;

        const payoutHtml = data.payout_configured
            ? `<button class="action-btn bounce" onclick="billingPayoutModal()" style="width: 100%; background: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary); border-radius: 14px; padding: 14px; font-weight: 600; font-size: 15px;">
                <span class="material-symbols-rounded" style="font-size: 20px;">payments</span> Вывести деньги
            </button>`
            : `<div style="font-size: 13px; opacity: 0.6; text-align: center; background: rgba(255,255,255,0.04); border-radius: 14px; padding: 12px;">Вывод не подключён: нет Payout-секрета Platega</div>`;

        const ap = data.autopayout || {};
        const autopayoutHtml = data.payout_configured ? `
            <button class="action-btn bounce" onclick="billingAutopayoutModal()" style="display: flex; align-items: center; gap: 10px; width: 100%; background: rgba(255,255,255,0.04); border-radius: 14px; padding: 12px; color: #fff; text-align: left;">
                <span class="material-symbols-rounded" style="font-size: 20px; color: ${ap.enabled ? '#4CAF50' : 'rgba(255,255,255,0.5)'};">autorenew</span>
                <div style="flex: 1; min-width: 0;">
                    <div style="font-size: 14px; font-weight: 600;">Автовывод · ${ap.enabled ? 'вкл' : 'выкл'}</div>
                    <div style="font-size: 11px; opacity: 0.55;">порог ${fmtRub(ap.threshold || 0)}${ap.last_amount ? ` · последний: ${fmtRub(ap.last_amount)}` : ''}</div>
                </div>
                <span class="material-symbols-rounded" style="font-size: 18px; opacity: 0.5;">chevron_right</span>
            </button>` : '';

        container.innerHTML = `
            <div class="billing-section billing-sec-balances" style="background: var(--panel-bg); border-radius: 24px; padding: 18px; display: flex; flex-direction: column; gap: 12px;">
                <div style="font-size: 12px; opacity: 0.55; text-transform: uppercase; letter-spacing: 0.5px;">Балансы</div>
                ${balancesHtml}
                <div style="font-size: 12px; opacity: 0.55; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px;">Вывод</div>
                ${payoutHtml}
                ${autopayoutHtml}
            </div>

            <div class="billing-section billing-sec-servers" style="background: var(--panel-bg); border-radius: 24px; padding: 18px; display: flex; flex-direction: column; gap: 12px;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="font-size: 12px; opacity: 0.55; text-transform: uppercase; letter-spacing: 0.5px;">Прибыль за месяц</div>
                    <div style="font-size: 20px; font-weight: 700; color: ${(data.month_profit || 0) >= 0 ? '#4CAF50' : '#EF5350'};">${fmtRub(data.month_profit)}</div>
                </div>
                <div style="font-size: 12px; opacity: 0.55;">Сервера: ${fmtRub(data.servers ? data.servers.monthly_total : 0)}/мес</div>
                <div style="display: flex; flex-direction: column; gap: 8px;">${serversHtml}</div>
                <button class="action-btn bounce" onclick="billingServerModal()" style="background: rgba(255,255,255,0.06); border-radius: 14px; padding: 12px; color: #fff; font-size: 14px;">
                    <span class="material-symbols-rounded" style="font-size: 18px;">add</span> Добавить сервер
                </button>
                <div style="font-size: 12px; opacity: 0.55; margin-top: 4px;">Внеплановые${ledgerTotal ? ` · ${ledgerTotal > 0 ? '+' : ''}${fmtRub(ledgerTotal)}` : ''}</div>
                <div style="display: flex; flex-direction: column; gap: 8px;">${ledgerHtml}</div>
                <button class="action-btn bounce" onclick="billingLedgerModal()" style="background: rgba(255,255,255,0.06); border-radius: 14px; padding: 12px; color: #fff; font-size: 14px;">
                    <span class="material-symbols-rounded" style="font-size: 18px;">edit_note</span> Добавить запись
                </button>
            </div>

            <!-- Доходы идут третьими: в двухколоночной masonry-раскладке
                 колонки собираются как {Балансы, Прибыль} | {Доходы, Плательщики},
                 поэтому Балансы и Доходы оказываются на одном уровне сверху. -->
            <div class="billing-section billing-sec-income" style="background: var(--panel-bg); border-radius: 24px; padding: 18px; display: flex; flex-direction: column; gap: 12px;">${billingIncomeHtml(data)}</div>

            <div class="billing-section billing-sec-payers" style="background: var(--panel-bg); border-radius: 24px; padding: 18px; display: flex; flex-direction: column; gap: 12px;">
                <div style="display: flex; align-items: center; gap: 6px; font-size: 12px; opacity: 0.55; text-transform: uppercase; letter-spacing: 0.5px;">
                    <span class="material-symbols-rounded" style="font-size: 15px;">group</span>Плательщики · топ
                </div>
                <div class="billing-payers" style="display: flex; flex-direction: column; gap: 8px;">${payersHtml}</div>
            </div>

            `;
        renderBillingChart(data);
        renderBillingPayers();
    }

    function billingPayerRow(p) {
        const label = p.username ? `@${p.username}` : `ID ${p.telegram_id}`;
        const initial = ((p.username || 'U')[0] || 'U').toUpperCase();
        const avatar = p.avatar_url
            ? `<img src="/user/avatar-url-proxy/?url=${escapeHtml(encodeURIComponent(p.avatar_url))}" alt="" loading="lazy" style="width: 100%; height: 100%; object-fit: cover;" onerror="billingAvatarFallback(this)">`
            : `<span style="font-size: 18px; font-weight: 600;">${escapeHtml(initial)}</span>`;
            return `
            <div class="billing-payer-row">
                <button class="bounce billing-avatar-btn" data-initial="${escapeHtml(initial)}" onclick="openPayerChat(${p.telegram_id}, '${escapeJsAttr(p.username || '')}')" title="Открыть чат">${avatar}</button>
                <div style="flex: 1; min-width: 0;">
                    <div style="font-size: 14px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(label)}</div>
                    <div style="font-size: 12px; opacity: 0.55;">ID ${p.telegram_id} · ${p.count} пл.</div>
                </div>
                <div style="font-size: 15px; font-weight: 700; color: #4CAF50; white-space: nowrap;">+${fmtRub(p.total)}</div>
                <button class="bounce" onclick="billingPayerHide(${p.telegram_id})" title="Скрыть из статистики" style="background: transparent; border: none; border-radius: 8px; padding: 4px; color: rgba(255,255,255,0.35); display: flex;"><span class="material-symbols-rounded" style="font-size: 15px;">visibility_off</span></button>
            </div>`;
    }

    function renderBillingPayers() {
        const rows = document.getElementById('billing-payer-rows');
        const hiddenBox = document.getElementById('billing-payer-hidden');
        if (!rows || !hiddenBox) return;
        const data = window._billingData || {};
        const blacklisted = new Set(data.blacklisted || []);
        const q = (window._billingPayersQuery || '').toLowerCase();
        const all = (window._billingPayers || []).filter(p =>
            !q || (p.username && p.username.toLowerCase().includes(q)) || String(p.telegram_id).includes(q)
        );
        const page = Math.max(1, window._billingPayersPage || 1);
        const shown = all.slice(0, page * 10);
        rows.innerHTML = shown.length ? shown.map(billingPayerRow).join('')
            : `<div style="font-size: 13px; opacity: 0.55; text-align: center; padding: 8px;">${q ? 'Ничего не найдено' : 'Пока никто не платил'}</div>`;
        let extra = '';
        if (all.length > page * 10) {
            const left = all.length - page * 10;
            extra += `<button class="action-btn bounce" onclick="billingPayersMore()" style="width: 100%; grid-column: 1 / -1; background: rgba(255,255,255,0.06); border-radius: 12px; padding: 10px; color: #fff; font-size: 13px;">Загрузить ещё (${left})</button>`;
        } else if (page > 1 && all.length > 10) {
            extra += `<button class="action-btn bounce" onclick="billingPayersCollapse()" style="width: 100%; grid-column: 1 / -1; background: rgba(255,255,255,0.06); border-radius: 12px; padding: 10px; color: #fff; font-size: 13px;">Свернуть</button>`;
        }
        rows.insertAdjacentHTML('beforeend', extra);
        hiddenBox.innerHTML = blacklisted.size ? `
            <div style="font-size: 12px; opacity: 0.55; margin-top: 4px;">Скрытые (${blacklisted.size}):</div>
            <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px;">
                ${[...blacklisted].map(id => `
                    <button class="bounce" onclick="billingPayerRestore(${id})" title="Вернуть в статистику" style="display: flex; align-items: center; gap: 4px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 6px 10px; color: rgba(255,255,255,0.7); font-size: 12px;">
                        ID ${id}<span class="material-symbols-rounded" style="font-size: 15px;">visibility</span>
                    </button>`).join('')}
            </div>` : '';
    }

    window.billingPayerSearch = (value) => {
        window._billingPayersQuery = value || '';
        window._billingPayersPage = 1;
        renderBillingPayers();
    };

    window.billingPayersMore = () => {
        window._billingPayersPage = (window._billingPayersPage || 1) + 1;
        billingHaptic();
        renderBillingPayers();
    };

    window.billingPayersCollapse = () => {
        window._billingPayersPage = 1;
        billingHaptic();
        renderBillingPayers();
    };

    async function billingBlacklist(action, telegramId) {
        try {
            const resp = await fetch('/shop/billing-blacklist-api/', {
                method: 'POST',
                body: billingFormData({ action, telegram_id: telegramId })
            });
            const data = await resp.json();
            if (!data.success) throw new Error(data.error);
            billingHaptic('success');
            fetchBilling();
        } catch (e) {
            showModal({ title: 'Ошибка', message: String((e && e.message) || e), icon: 'error', actionText: 'Ок', onAction: hideModal });
        }
    }

    window.billingPayerHide = (telegramId) => {
        billingBlacklist('add', telegramId);
    };

    window.billingPayerRestore = (telegramId) => {
        billingBlacklist('remove', telegramId);
    };

    window.billingServerModal = (id) => {
        const data = window._billingData;
        const servers = (data && data.servers && data.servers.servers) || [];
        const s = id ? servers.find(x => x.id === id) : null;
        const customHtml = `
            <div style="display: flex; flex-direction: column; gap: 10px; width: 100%; text-align: left;">
                <label style="font-size: 12px; opacity: 0.6;">Название
                    <input id="billing-server-name" class="modal-input" style="text-align: left; margin-top: 4px;" value="${s ? escapeHtml(s.name) : ''}" placeholder="VPS-1 · Нидерланды">
                </label>
                <div style="display: flex; gap: 10px;">
                    <label style="font-size: 12px; opacity: 0.6; flex: 1;">₽/мес
                        <input id="billing-server-cost" class="modal-input" style="text-align: left; margin-top: 4px;" type="number" min="1" value="${s ? s.monthly_cost : ''}" placeholder="500">
                    </label>
                    <label style="font-size: 12px; opacity: 0.6; flex: 1;">День оплаты
                        <input id="billing-server-day" class="modal-input" style="text-align: left; margin-top: 4px;" type="number" min="1" max="31" value="${s ? s.pay_day : ''}" placeholder="15">
                    </label>
                </div>
            </div>`;
        showModal({
            title: s ? 'Изменить сервер' : 'Новый сервер',
            message: '',
            icon: 'dns',
            customHtml: customHtml,
            actionText: 'Сохранить',
            onAction: () => billingServerSave(id || null),
            closeBtnText: 'Отмена'
        });
    };

    async function billingServerSave(id) {
        const name = (document.getElementById('billing-server-name') || {}).value || '';
        const cost = (document.getElementById('billing-server-cost') || {}).value || '';
        const day = (document.getElementById('billing-server-day') || {}).value || '';
        try {
            const resp = await fetch('/shop/billing-server-api/', {
                method: 'POST',
                body: billingFormData({ action: id ? 'update' : 'create', id: id || '', name, monthly_cost: cost, pay_day: day })
            });
            const data = await resp.json();
            if (!data.success) throw new Error(data.error);
            billingHaptic('success');
            fetchBilling();
        } catch (e) {
            showModal({ title: 'Ошибка', message: String((e && e.message) || e), icon: 'error', actionText: 'Ок', onAction: hideModal });
        }
    }

    window.billingServerDelete = (id) => {
        showModal({
            title: 'Удалить сервер?',
            message: 'Запись о расходах будет удалена.',
            icon: 'delete',
            actionText: 'Удалить',
            onAction: async () => {
                try {
                    const resp = await fetch('/shop/billing-server-api/', {
                        method: 'POST',
                        body: billingFormData({ action: 'delete', id })
                    });
                    const data = await resp.json();
                    if (!data.success) throw new Error(data.error);
                    billingHaptic('success');
                    fetchBilling();
                } catch (e) {
                    showModal({ title: 'Ошибка', message: String((e && e.message) || e), icon: 'error', actionText: 'Ок', onAction: hideModal });
                }
            },
            closeBtnText: 'Отмена'
        });
    };

    window._billingLedgerType = 'exp';

    window.billingLedgerType = (type) => {
        window._billingLedgerType = type;
        const exp = document.getElementById('billing-ledger-type-exp');
        const inc = document.getElementById('billing-ledger-type-inc');
        if (exp) {
            exp.style.border = type === 'exp' ? '1px solid #EF5350' : '1px solid rgba(255,255,255,0.1)';
            exp.style.background = type === 'exp' ? 'rgba(239,83,80,0.12)' : 'rgba(255,255,255,0.04)';
        }
        if (inc) {
            inc.style.border = type === 'inc' ? '1px solid #4CAF50' : '1px solid rgba(255,255,255,0.1)';
            inc.style.background = type === 'inc' ? 'rgba(76,175,80,0.12)' : 'rgba(255,255,255,0.04)';
        }
    };

    window.billingLedgerModal = () => {
        window._billingLedgerType = 'exp';
        const today = new Date().toISOString().slice(0, 10);
        const customHtml = `
            <div style="display: flex; flex-direction: column; gap: 10px; width: 100%; text-align: left;">
                <div style="display: flex; gap: 10px;">
                    <button id="billing-ledger-type-exp" class="bounce" onclick="billingLedgerType('exp')" style="flex: 1; border: 1px solid #EF5350; background: rgba(239,83,80,0.12); color: #fff; border-radius: 12px; padding: 10px; font-size: 14px;">Расход −</button>
                    <button id="billing-ledger-type-inc" class="bounce" onclick="billingLedgerType('inc')" style="flex: 1; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.04); color: #fff; border-radius: 12px; padding: 10px; font-size: 14px;">Доход +</button>
                </div>
                <label style="font-size: 12px; opacity: 0.6;">Описание
                    <input id="billing-ledger-name" class="modal-input" style="text-align: left; margin-top: 4px;" placeholder="Такси до ДЦ / перевод на карту">
                </label>
                <div style="display: flex; gap: 10px;">
                    <label style="font-size: 12px; opacity: 0.6; flex: 1;">Сумма, ₽
                        <input id="billing-ledger-amount" class="modal-input" style="text-align: left; margin-top: 4px;" type="number" min="1" placeholder="1000">
                    </label>
                    <label style="font-size: 12px; opacity: 0.6; flex: 1;">Дата
                        <input id="billing-ledger-date" class="modal-input" style="text-align: left; margin-top: 4px;" type="date" value="${today}">
                    </label>
                </div>
            </div>`;
        showModal({
            title: 'Новая запись',
            message: '',
            icon: 'edit_note',
            customHtml: customHtml,
            actionText: 'Сохранить',
            onAction: () => billingLedgerSave(),
            closeBtnText: 'Отмена'
        });
    };

    async function billingLedgerSave() {
        const name = (document.getElementById('billing-ledger-name') || {}).value || '';
        const rawAmount = parseFloat((document.getElementById('billing-ledger-amount') || {}).value || '0');
        const date = (document.getElementById('billing-ledger-date') || {}).value || '';
        if (!name.trim() || !rawAmount || rawAmount <= 0) {
            showModal({ title: 'Ошибка', message: 'Укажите описание и сумму.', icon: 'error', actionText: 'Ок', onAction: hideModal });
            return;
        }
        const amount = window._billingLedgerType === 'inc' ? Math.abs(rawAmount) : -Math.abs(rawAmount);
        try {
            const resp = await fetch('/shop/billing-ledger-api/', {
                method: 'POST',
                body: billingFormData({ action: 'create', name: name.trim(), amount, entry_date: date })
            });
            const data = await resp.json();
            if (!data.success) throw new Error(data.error);
            billingHaptic('success');
            fetchBilling();
        } catch (e) {
            showModal({ title: 'Ошибка', message: String((e && e.message) || e), icon: 'error', actionText: 'Ок', onAction: hideModal });
        }
    }

    window.billingLedgerDelete = (id) => {
        showModal({
            title: 'Удалить запись?',
            message: '',
            icon: 'delete',
            actionText: 'Удалить',
            onAction: async () => {
                try {
                    const resp = await fetch('/shop/billing-ledger-api/', {
                        method: 'POST',
                        body: billingFormData({ action: 'delete', id })
                    });
                    const data = await resp.json();
                    if (!data.success) throw new Error(data.error);
                    billingHaptic('success');
                    fetchBilling();
                } catch (e) {
                    showModal({ title: 'Ошибка', message: String((e && e.message) || e), icon: 'error', actionText: 'Ок', onAction: hideModal });
                }
            },
            closeBtnText: 'Отмена'
        });
    };

    window.billingServerPaid = async (id) => {
        try {
            const resp = await fetch('/shop/billing-server-api/', {
                method: 'POST',
                body: billingFormData({ action: 'mark_paid', id })
            });
            const data = await resp.json();
            if (!data.success) throw new Error(data.error);
            billingHaptic('success');
            fetchBilling();
        } catch (e) {
            showModal({ title: 'Ошибка', message: String((e && e.message) || e), icon: 'error', actionText: 'Ок', onAction: hideModal });
        }
    };

    window.billingPayoutFillAll = () => {
        const data = window._billingData || {};
        const input = document.getElementById('billing-payout-amount');
        if (input && data.payout_all_amount) input.value = data.payout_all_amount;
        billingHaptic();
    };

    window.billingPayoutModal = () => {
        const data = window._billingData || {};
        const mode = data.payout_mode || (data.payout_configured ? 'api' : 'off');
        const pmin = data.payout_min || 1000;
        const pmax = data.payout_max || 87500;
        const feeUsd = data.payout_fee_usd || 0.5;
        const allAmount = data.payout_all_amount || 0;
        const dest = data.payout_dest_masked || '';
        const cards = data.payout_cards || [];
        const preset = data.payout_preset_card_id;
        const options = cards.map(c => {
            const label = `${c.masked || ''} ${c.brand || ''} ${c.label || ''}`.trim();
            const sel = preset && preset === c.cardId ? 'selected' : '';
            return `<option value="${escapeHtml(c.cardId)}" ${sel}>${escapeHtml(label)}</option>`;
        }).join('');
        const customHtml = `
            <div style="display: flex; flex-direction: column; gap: 10px; width: 100%; text-align: left;">
                <label style="font-size: 12px; opacity: 0.6;">Сумма, ₽ (${pmin}–${pmax})
                    <input id="billing-payout-amount" class="modal-input" style="text-align: left; margin-top: 4px;" type="number" min="${pmin}" max="${pmax}" value="${allAmount >= pmin ? allAmount : ''}" placeholder="5000">
                </label>
                ${mode === 'ui' ? (allAmount
                    ? `<button class="action-btn bounce" onclick="billingPayoutFillAll()" style="width: 100%; background: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary); border-radius: 14px; padding: 14px; font-weight: 600; font-size: 15px;">
                        <span class="material-symbols-rounded" style="font-size: 20px;">vertical_align_top</span> Вывести максимум · ${fmtRub(allAmount)}
                    </button>`
                    : `<div style="font-size: 13px; opacity: 0.6; text-align: center; background: rgba(255,255,255,0.04); border-radius: 14px; padding: 12px;">Максимум недоступен: баланс ниже минимума ${fmtRub(pmin)}</div>`) : ''}
                ${mode === 'api' && cards.length ? `<label style="font-size: 12px; opacity: 0.6;">Карта
                    <select id="billing-payout-card" class="modal-input" style="text-align: left; margin-top: 4px; background: rgba(255,255,255,0.05);">
                        ${options}
                        <option value="">Ввести номер вручную…</option>
                    </select>
                </label>` : ''}
                ${mode === 'api' ? `<label id="billing-payout-pan-wrap" style="font-size: 12px; opacity: 0.6; ${cards.length ? 'display: none;' : ''}">Номер карты (16 цифр)
                    <input id="billing-payout-pan" class="modal-input" style="text-align: left; margin-top: 4px;" inputmode="numeric" maxlength="19" placeholder="2200 0000 0000 0000">
                </label>` : ''}
                ${mode === 'ui' ? `<div style="font-size: 12px; opacity: 0.6; background: rgba(255,255,255,0.04); border-radius: 12px; padding: 10px 12px;">На карту ${escapeHtml(dest || 'по умолчанию')} · комиссия ${feeUsd} USD (курс ~${Number(data.usd_rub_rate || 0).toFixed(2)}) · заявку выполнит браузер, итог придёт сюда и в Telegram</div>` : ''}
            </div>`;
        showModal({
            title: 'Вывод денег',
            message: mode === 'ui' ? 'Вывод через сайт Platega.' : 'Деньги спишутся с USDT-баланса Platega.',
            icon: 'payments',
            customHtml: customHtml,
            actionText: 'Далее',
            onAction: () => billingPayoutConfirm(),
            closeBtnText: 'Отмена'
        });
        const sel = document.getElementById('billing-payout-card');
        if (sel) {
            sel.onchange = () => {
                const wrap = document.getElementById('billing-payout-pan-wrap');
                if (wrap) wrap.style.display = sel.value ? 'none' : '';
            };
        }
    };

    async function billingPayoutPoll(jobId) {
        // Опрос статуса браузерной заявки: максимум 6 минут,
        // дальше итог придёт в Telegram.
        const t0 = Date.now();
        showLoading('Выполняю вывод...');
        while (Date.now() - t0 < 6 * 60 * 1000) {
            await new Promise(r => setTimeout(r, 5000));
            let st = null;
            try {
                const resp = await fetch('/shop/billing-payout-job-api/', {
                    method: 'POST',
                    body: billingFormData({ job_id: jobId })
                });
                st = await resp.json();
                if (!st.success) throw new Error(st.error);
            } catch (e) {
                hideLoading();
                showModal({ title: 'Ошибка', message: String((e && e.message) || e), icon: 'error', actionText: 'Ок', onAction: hideModal });
                return;
            }
            if (st.status === 'DONE') {
                hideLoading();
                billingHaptic('success');
                showModal({
                    title: 'Вывод создан!',
                    message: `Выведено ${st.amount} ₽ на ${st.dest_masked || 'карту'}. ${st.page_text || ''}`,
                    icon: 'check_circle',
                    actionText: 'Ок',
                    onAction: hideModal
                });
                fetchBilling();
                return;
            }
            if (st.status === 'FAILED') {
                hideLoading();
                showModal({ title: 'Ошибка', message: String(st.error || 'неизвестная ошибка'), icon: 'error', actionText: 'Ок', onAction: hideModal });
                return;
            }
        }
        hideLoading();
        showModal({ title: 'Всё ещё выполняется', message: 'Вывод занял больше 6 минут. Итог придёт в Telegram.', icon: 'schedule', actionText: 'Ок', onAction: hideModal });
        fetchBilling();
    }

    async function billingPayoutConfirm() {
        const data = window._billingData || {};
        const mode = data.payout_mode || (data.payout_configured ? 'api' : 'off');
        const pmin = data.payout_min || 1000;
        const pmax = data.payout_max || 87500;
        const amount = parseInt((document.getElementById('billing-payout-amount') || {}).value || '0', 10);
        const sel = document.getElementById('billing-payout-card');
        const cardId = sel && sel.value ? sel.value : '';
        const pan = ((document.getElementById('billing-payout-pan') || {}).value || '').replace(/\D/g, '');
        if (!amount || amount < pmin || amount > pmax) {
            showModal({ title: 'Ошибка', message: `Сумма — от ${pmin} до ${pmax} ₽.`, icon: 'error', actionText: 'Ок', onAction: hideModal });
            return;
        }
        if (mode === 'api' && !cardId && pan.length !== 16) {
            showModal({ title: 'Ошибка', message: 'Укажите карту или номер из 16 цифр.', icon: 'error', actionText: 'Ок', onAction: hideModal });
            return;
        }
        const dest = mode === 'ui'
            ? `карту ${data.payout_dest_masked || 'по умолчанию'} (выполнит браузер)`
            : (cardId ? 'сохранённую карту' : `карту **** ${pan.slice(-4)}`);
        showModal({
            title: 'Подтверждение',
            message: `Вывести ${amount} ₽ на ${dest}?`,
            icon: 'warning',
            actionText: 'Вывести',
            onAction: async () => {
                if (window._payoutInFlight) return false;
                window._payoutInFlight = true;
                showLoading('Выполняю вывод...');
                try {
                    const resp = await fetch('/shop/billing-payout-api/', {
                        method: 'POST',
                        body: billingFormData({ amount, card_id: cardId, card_number: cardId ? '' : pan })
                    });
                    const data = await resp.json();
                    hideLoading();
                    window._payoutInFlight = false;
                    if (!data.success) throw new Error(data.error);
                    if (data.mode === 'ui' && data.job_id) {
                        billingPayoutPoll(data.job_id);
                        return;
                    }
                    billingHaptic('success');
                    showModal({
                        title: 'Вывод создан!',
                        message: `Статус: ${data.status || 'CREATED'}. Карта: ${data.card_masked || ''}. Списано USDT: ${data.amount_usdt_debited || '—'}.`,
                        icon: 'check_circle',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                    fetchBilling();
                } catch (e) {
                    hideLoading();
                    window._payoutInFlight = false;
                    showModal({ title: 'Ошибка', message: String((e && e.message) || e), icon: 'error', actionText: 'Ок', onAction: hideModal });
                }
            },
            closeBtnText: 'Отмена'
        });
    }

    window._billingAutopayoutOn = false;

    window.billingAutopayoutToggle = (on) => {
        window._billingAutopayoutOn = !!on;
        const bOn = document.getElementById('billing-ap-on');
        const bOff = document.getElementById('billing-ap-off');
        if (bOn) {
            bOn.style.border = on ? '1px solid #4CAF50' : '1px solid rgba(255,255,255,0.1)';
            bOn.style.background = on ? 'rgba(76,175,80,0.12)' : 'rgba(255,255,255,0.04)';
        }
        if (bOff) {
            bOff.style.border = !on ? '1px solid #4CAF50' : '1px solid rgba(255,255,255,0.1)';
            bOff.style.background = !on ? 'rgba(76,175,80,0.12)' : 'rgba(255,255,255,0.04)';
        }
    };

    window.billingAutopayoutModal = () => {
        const ap = (window._billingData && window._billingData.autopayout) || {};
        window._billingAutopayoutOn = !!ap.enabled;
        const lastLine = ap.last_amount
            ? `Последний автовывод: ${fmtRub(ap.last_amount)}${ap.last_at ? ` · ${ap.last_at.slice(0, 10)}` : ''}`
            : 'Автовыводов ещё не было';
        const customHtml = `
            <div style="display: flex; flex-direction: column; gap: 10px; width: 100%; text-align: left;">
                <div style="display: flex; gap: 10px;">
                    <button id="billing-ap-on" class="bounce" onclick="billingAutopayoutToggle(true)" style="flex: 1; border-radius: 12px; padding: 10px; color: #fff; font-size: 14px;">Вкл</button>
                    <button id="billing-ap-off" class="bounce" onclick="billingAutopayoutToggle(false)" style="flex: 1; border-radius: 12px; padding: 10px; color: #fff; font-size: 14px;">Выкл</button>
                </div>
                <label style="font-size: 12px; opacity: 0.6;">Порог баланса, ₽
                    <input id="billing-ap-threshold" class="modal-input" style="text-align: left; margin-top: 4px;" type="number" min="1000" value="${ap.threshold || ''}" placeholder="10000">
                </label>
                <label style="font-size: 12px; opacity: 0.6;">Проверять каждые, мин
                    <input id="billing-ap-check" class="modal-input" style="text-align: left; margin-top: 4px;" type="number" min="1" max="1440" value="${ap.check_min || ''}" placeholder="15">
                </label>
                <label style="font-size: 12px; opacity: 0.6;">Пауза после вывода, мин
                    <input id="billing-ap-cooldown" class="modal-input" style="text-align: left; margin-top: 4px;" type="number" min="0" max="2880" value="${ap.cooldown_min || ''}" placeholder="60">
                </label>
                <div style="font-size: 12px; opacity: 0.55;">${lastLine}</div>
            </div>`;
        showModal({
            title: 'Автовывод',
            message: '',
            icon: 'autorenew',
            customHtml: customHtml,
            actionText: 'Сохранить',
            onAction: () => billingAutopayoutSave(),
            closeBtnText: 'Отмена'
        });
        billingAutopayoutToggle(window._billingAutopayoutOn);
    };

    async function billingAutopayoutSave() {
        const payload = {
            enabled: window._billingAutopayoutOn ? '1' : '0',
            threshold: (document.getElementById('billing-ap-threshold') || {}).value || '',
            check_min: (document.getElementById('billing-ap-check') || {}).value || '',
            cooldown_min: (document.getElementById('billing-ap-cooldown') || {}).value || '',
        };
        try {
            const resp = await fetch('/shop/billing-autopayout-api/', {
                method: 'POST',
                body: billingFormData(payload)
            });
            const data = await resp.json();
            if (!data.success) throw new Error(data.error);
            billingHaptic('success');
            fetchBilling();
        } catch (e) {
            showModal({ title: 'Ошибка', message: String((e && e.message) || e), icon: 'error', actionText: 'Ок', onAction: hideModal });
        }
    }

    window.handleTogglePreference = async (prefType, value) => {
        const tg = window.Telegram?.WebApp;
        const userId = window.authenticatedUserId;

        if (!userId && !tg?.initData) {
            console.warn('Cannot update preference: No userId and no initData');
            return;
        }

        try {
            const formData = new FormData();
            formData.append('type', prefType);
            formData.append('value', value);
            formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

            if (tg?.initData) {
                formData.append('init_data', tg.initData);
            }

            const response = await fetch('/shop/update-preferences-api/', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                console.error('Failed to update preference');
                // Could optionally revert the toggle UI here if needed
            } else {
                if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
                    window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
                }
            }
        } catch (e) {
            console.error('Error updating preference:', e);
        }
    };

    async function startDataSync() {
        const tg = window.Telegram?.WebApp;

        window.syncNow = async () => {
            const userId = window.authenticatedUserId;
            
            // Allow sync if we have either userId OR initData (Mini App mode)
            if (!userId && !tg?.initData) {
                console.warn('Sync skipped: No userId and no initData');
                return;
            }

            const formData = new FormData();

            if (tg?.initData) {
                formData.append('init_data', tg.initData);
            }
            formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

            try {
                const response = await fetch('/shop/sync-data-api/', {
                    method: 'POST',
                    body: formData,
                    cache: 'no-store',
                });
                if (response.ok) {
                    const data = await response.json();
                    updateUIWithSyncData(data);
                }
            } catch (e) {
                console.error('Manual sync failed:', e);
            }
        };

        // Poll every 10 seconds
        setInterval(window.syncNow, 10000);

        // Initial sync attempt
        window.syncNow();
    }

    // --- Instruction Carousel Logic ---
    let currentInstrSlide = 0;

    let galleriesInitialized = false;

    function initInstructionGalleries() {
        if (galleriesInitialized) return;
        galleriesInitialized = true;

        const galleries = document.querySelectorAll('.instruction-images');
        galleries.forEach(gallery => {
            let isDown = false;
            let startX;
            let scrollLeft;
            let hasDragged = false; // track if real drag happened (to block click)

            // Prevent native image drag inside gallery
            gallery.querySelectorAll('img').forEach(img => {
                img.setAttribute('draggable', 'false');
                img.addEventListener('dragstart', e => e.preventDefault());
            });

            gallery.addEventListener('mousedown', (e) => {
                isDown = true;
                hasDragged = false;
                gallery.classList.add('dragging');
                startX = e.pageX - gallery.offsetLeft;
                scrollLeft = gallery.scrollLeft;
                e.preventDefault(); // prevent text/image selection
            });

            gallery.addEventListener('mouseleave', () => {
                if (!isDown) return;
                isDown = false;
                gallery.classList.remove('dragging');
                gallery.style.scrollSnapType = 'x mandatory';
            });

            gallery.addEventListener('mouseup', () => {
                isDown = false;
                gallery.classList.remove('dragging');
                gallery.style.scrollSnapType = 'x mandatory';
            });

            gallery.addEventListener('mousemove', (e) => {
                if (!isDown) return;
                e.preventDefault();
                const x = e.pageX - gallery.offsetLeft;
                const delta = x - startX;
                // Only disable snap once actual drag starts (threshold 5px)
                if (Math.abs(delta) > 5) {
                    hasDragged = true;
                    gallery.style.scrollSnapType = 'none';
                }
                gallery.scrollLeft = scrollLeft - delta;
            });

            // Block click on images if we actually dragged
            gallery.addEventListener('click', (e) => {
                if (hasDragged) e.stopPropagation();
            }, true);

            gallery.style.cursor = 'grab';
            gallery.style.userSelect = 'none';

            // Dot updates on scroll
            gallery.addEventListener('scroll', () => {
                const images = gallery.querySelectorAll('img');
                if (images.length === 0) return;
                const imageWidth = gallery.clientWidth * 0.9;
                let activeIndex = Math.round(gallery.scrollLeft / imageWidth);
                if (activeIndex < 0) activeIndex = 0;
                if (activeIndex >= images.length) activeIndex = images.length - 1;

                const dotsContainer = gallery.nextElementSibling;
                if (dotsContainer && dotsContainer.classList.contains('gallery-dots')) {
                    dotsContainer.querySelectorAll('.dot').forEach((dot, idx) => {
                        dot.classList.toggle('active', idx === activeIndex);
                    });
                }
            });
        });

        // Drag-to-swipe for the main carousel track on PC
        const track = document.getElementById('instruction-track');
        const container = track ? track.parentElement : null;
        if (track && container) {
            let trackDown = false;
            let trackStartX;
            let trackDragged = false;

            container.addEventListener('mousedown', (e) => {
                // Only start if not inside a gallery
                if (e.target.closest('.instruction-images')) return;
                trackDown = true;
                trackDragged = false;
                trackStartX = e.pageX;
                e.preventDefault();
            });

            window.addEventListener('mouseup', () => {
                if (!trackDown) return;
                trackDown = false;
            });

            window.addEventListener('mousemove', (e) => {
                if (!trackDown) return;
                const delta = e.pageX - trackStartX;
                if (Math.abs(delta) > 30) {
                    trackDragged = true;
                    trackDown = false;
                    if (delta < 0) {
                        window.nextInstructionSlide();
                    } else {
                        window.prevInstructionSlide();
                    }
                }
            });

            // Block click events that follow a drag
            container.addEventListener('click', (e) => {
                if (trackDragged) {
                    e.stopPropagation();
                    trackDragged = false;
                }
            }, true);
        }
    }

    window.showInstructions = () => {
        const overlay = document.getElementById('instruction-overlay');
        if (overlay) {
            // Move to body to prevent transform containment issues on mobile
            if (overlay.parentElement !== document.body) {
                document.body.appendChild(overlay);
            }

            // Reset slide BEFORE making overlay visible to avoid
            // accidental clicks on slide-4's openSubLink() button
            currentInstrSlide = 0;

            // Sync the app picker (Incy / Happ) first so the carousel
            // knows whether "Шаг 3" is hidden (Incy has 3 steps).
            renderAppSelection();
            updateInstructionCarousel();

            overlay.style.display = 'flex';
            // Temporarily block pointer events on slides during open animation
            const track = document.getElementById('instruction-track');
            if (track) {
                track.style.pointerEvents = 'none';
                setTimeout(() => { track.style.pointerEvents = ''; }, 350);
            }
            // Force reflow
            void overlay.offsetWidth;
            overlay.classList.add('active');

            initInstructionGalleries();
            try {
                detectAndHighlightPlatform();
            } catch (e) { console.error(e); }
        }
    };

    // Apps offered in the instruction "Установка" step.
    const APP_DATA = {
        incy: {
            name: 'Incy',
            scheme: 'incy://add/',
            links: {
                ios: 'https://apps.apple.com/us/app/incy/id6756943388',
                mac: 'https://apps.apple.com/us/app/incy/id6756943388',
                android: 'https://play.google.com/store/apps/details?id=llc.itdev.incy&pli=1',
                windows: 'https://github.com/INCY-DEV/incy-platforms/releases',
            },
        },
        happ: {
            name: 'Happ',
            scheme: 'happ://add/',
            links: {
                ios: 'https://apps.apple.com/us/app/happ-proxy-utility/id6504287215',
                mac: 'https://apps.apple.com/us/app/happ-proxy-utility/id6504287215',
                android: 'https://play.google.com/store/apps/details?id=com.happproxy',
                windows: 'https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe',
            },
        },
    };
    window._selectedApp = 'incy';

    function updateInstrImages(app) {
        const gallery = document.getElementById('instr-frag-gallery');
        if (!gallery) return;
        const imgs = gallery.querySelectorAll('img');
        const srcs = app === 'incy'
            ? ['/static/insructions/INCY1.jpg', '/static/insructions/INCY2.jpg']
            : ['/static/insructions/settings.jpg', '/static/insructions/frag.jpg'];
        imgs.forEach((img, i) => {
            if (srcs[i]) img.src = srcs[i];
        });
    }

    function renderAppSelection() {
        const app = APP_DATA[window._selectedApp] ? window._selectedApp : 'incy';
        document.querySelectorAll('.app-card').forEach(card => {
            card.classList.toggle('selected', card.id === 'app-card-' + app);
        });
        const sub = document.getElementById('instr-app-subtitle');
        if (sub) sub.textContent = `Скачайте ${APP_DATA[app].name} для вашего устройства.`;
        updateInstrImages(app);

        // Всего 3 шага: установка, фрагментация, подключение.
        // ("Шаг 3: Авторизация Inbound" убран для всех приложений.)
        window._instrSlideCount = 3;
    }

    function getInstrSlideCount() {
        return (window._instrSlideCount > 0) ? window._instrSlideCount : 3;
    }

    window.selectApp = (app) => {
        if (!APP_DATA[app] || app === window._selectedApp) return;
        window._selectedApp = app;
        renderAppSelection();

        // Clamp the carousel to the valid range.
        if (currentInstrSlide > getInstrSlideCount() - 1) {
            currentInstrSlide = getInstrSlideCount() - 1;
            updateInstructionCarousel();
        }

        // Pop animation on the newly selected card.
        const card = document.getElementById('app-card-' + app);
        if (card) {
            card.classList.remove('pop');
            void card.offsetWidth;
            card.classList.add('pop');
        }

        // Slide-in animation for the switching download links.
        const links = document.getElementById('instr-platform-links');
        if (links) {
            links.classList.remove('switching');
            void links.offsetWidth;
            links.classList.add('switching');
        }
    };

    window.downloadHiddify = (platform) => {
        const app = APP_DATA[window._selectedApp] || APP_DATA.incy;
        const url = (app.links && app.links[platform]) || app.links.ios || '';
        if (!url) return;

        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.openLink(url);
        } else {
            window.open(url, '_blank');
        }
    };

    function detectAndHighlightPlatform() {
        let platform = 'unknown';
        const tgPlatform = window.Telegram?.WebApp?.platform;

        if (tgPlatform) {
            if (tgPlatform === 'android') platform = 'android';
            else if (tgPlatform === 'ios') platform = 'ios';
            else if (tgPlatform === 'macos' || tgPlatform === 'mac') platform = 'mac';
            else if (tgPlatform === 'windows' || tgPlatform === 'tdesktop') platform = 'windows';
        }

        if (platform === 'unknown') {
            const ua = navigator.userAgent.toLowerCase();
            if (/android/.test(ua)) platform = 'android';
            else if (/iphone|ipad|ipod/.test(ua)) platform = 'ios';
            else if (/mac/.test(ua)) platform = 'mac';
            else if (/win/.test(ua)) platform = 'windows';
        }

        document.querySelectorAll('.platform-btn').forEach(btn => {
            btn.classList.remove('recommended');
            const btnPlatform = btn.getAttribute('data-platform');
            if (btnPlatform === platform || (btnPlatform === 'ios' && platform === 'mac')) {
                btn.classList.add('recommended');
            }
        });

        // Рекомендуемый способ — наверх списка, чтобы был виден
        // без скролла даже на низких экранах.
        const links = document.getElementById('instr-platform-links');
        const top = links ? links.querySelector('.platform-btn.recommended') : null;
        if (top && links.firstElementChild !== top) {
            links.prepend(top);
        }
    }

    window.closeInstructions = () => {
        const overlay = document.getElementById('instruction-overlay');
        if (overlay) {
            overlay.classList.remove('active');
            setTimeout(() => {
                overlay.style.display = 'none';
            }, 300); // match transition duration
        }
    };

    window.nextInstructionSlide = () => {
        if (currentInstrSlide < getInstrSlideCount() - 1) {
            currentInstrSlide++;
            updateInstructionCarousel();
        }
    };

    window.skipToLastSlide = () => {
        currentInstrSlide = getInstrSlideCount() - 1;
        updateInstructionCarousel();
    };

    window.prevInstructionSlide = () => {
        if (currentInstrSlide > 0) {
            currentInstrSlide--;
            updateInstructionCarousel();
        }
    };

    function updateInstructionCarousel() {
        const track = document.getElementById('instruction-track');
        const dots = document.querySelectorAll('#carousel-dots .dot');
        const prevBtn = document.getElementById('instr-prev-btn');
        const nextBtn = document.getElementById('instr-next-btn');
        const skipBtn = document.getElementById('instr-skip-btn');
        const slideCount = getInstrSlideCount();

        if (track) {
            track.style.transform = `translateX(-${currentInstrSlide * (100 / slideCount)}%)`;
        }

        if (dots) {
            dots.forEach((dot, index) => {
                dot.style.display = index < slideCount ? '' : 'none';
                dot.classList.toggle('active', index === currentInstrSlide);
            });
        }

        if (prevBtn) {
            prevBtn.style.visibility = currentInstrSlide === 0 ? 'hidden' : 'visible';
        }

        if (skipBtn) {
            skipBtn.style.display = currentInstrSlide === slideCount - 1 ? 'none' : 'block';
        }

        if (nextBtn) {
            if (currentInstrSlide === slideCount - 1) {
                nextBtn.style.display = 'none';
            } else {
                nextBtn.style.display = 'block';

                if (currentInstrSlide === 0) {
                    nextBtn.innerText = 'Далее';
                    nextBtn.style.opacity = '1';
                    nextBtn.disabled = false;
                } else {
                    nextBtn.innerText = 'Я всё выполнил';

                    const currentSlideElement = document.querySelectorAll('.carousel-slide')[currentInstrSlide];
                    const gallery = currentSlideElement.querySelector('.instruction-images');

                    if (gallery) {
                        const checkScroll = () => {
                            if (gallery.clientWidth > 0 && gallery.scrollLeft + gallery.clientWidth >= gallery.scrollWidth - 10) {
                                return true;
                            }
                            return false;
                        };

                        if (checkScroll() || gallery.dataset.scrolledToEnd === 'true') {
                            nextBtn.style.opacity = '1';
                            nextBtn.disabled = false;
                        } else {
                            nextBtn.style.opacity = '0.3';
                            nextBtn.disabled = true;

                            if (!gallery.dataset.hasScrollListener) {
                                gallery.dataset.hasScrollListener = 'true';
                                gallery.addEventListener('scroll', () => {
                                    if (checkScroll()) {
                                        gallery.dataset.scrolledToEnd = 'true';
                                        // Update button if we are still on this slide
                                        const slides = Array.from(document.querySelectorAll('.carousel-slide'));
                                        if (currentInstrSlide === slides.indexOf(currentSlideElement)) {
                                            nextBtn.style.opacity = '1';
                                            nextBtn.disabled = false;
                                        }
                                    }
                                });
                            }
                        }
                    } else {
                        nextBtn.style.opacity = '1';
                        nextBtn.disabled = false;
                    }
                }
            }
        }
    }

    // Pending Payment Banner
    const pendingBanner = document.getElementById('pending-payment-banner');

    window.dismissPendingBanner = () => {
        if (pendingBanner) {
            pendingBanner.style.display = 'none';
        }
        const currentOrderId = lastPendingOrderId || getStoredOrderId();
        if (currentOrderId) {
            sessionStorage.setItem('dismissed_payment_banner_' + currentOrderId, 'true');
        }
    };

    function updatePendingBanner(hasPending) {
        if (!pendingBanner) return;
        const currentOrderId = lastPendingOrderId || getStoredOrderId();
        const isDismissed = currentOrderId && sessionStorage.getItem('dismissed_payment_banner_' + currentOrderId) === 'true';

        // Show the banner whenever a payment is pending (debug or not) so the
        // user can always return to the payment and see the timer.
        if (hasPending && !isDismissed) {
            pendingBanner.style.display = 'block';
        } else {
            pendingBanner.style.display = 'none';
        }
    }

    // Initial load check — restore the pending payment banner/timer if a
    // transaction was interrupted (e.g. user left the screen by accident).
    if (typeof HAS_PENDING_PAYMENT !== 'undefined') {
        updatePendingBanner(HAS_PENDING_PAYMENT);
    }

    // Extend sync data handler to include pending payment
    var lastPendingOrderId = null;

    const originalUpdateUI = updateUIWithSyncData;
    updateUIWithSyncData = function(data) {
        originalUpdateUI(data);

        var pp = data.pending_payment;

        // Payment gone → check what happened with the last known order
        if (paymentTimerInterval && !pp) {
            clearPaymentState();
            var checkId = lastPendingOrderId || getStoredOrderId();
            try { localStorage.removeItem(PENDING_PAYMENT_KEY); } catch(e) {}
            if (checkId) {
                fetch('/shop/check-payment-api/' + checkId + '/')
                    .then(function(r) { return r.json(); })
                    .then(async function(result) {
                        if (result.status === 'paid') {
                            await onTopupPaid(result.new_balance);
                        } else {
                            pendingPurchaseAfterTopup = null;
                            showModal({
                                title: 'Платёж не прошёл',
                                message: 'Время оплаты истекло или платёж отклонён.',
                                icon: 'error',
                                actionText: 'Ок',
                                onAction: hideModal
                            });
                        }
                    })
                    .catch(function() {
                        // fallback
                    });
            }
            lastPendingOrderId = null;
            return;
        }

        // No timer but server says payment exists → restore from server (cross-device / reload)
        if (!paymentTimerInterval && pp) {
            lastPendingOrderId = pp.order_id;
            var remaining = new Date(pp.expires_at).getTime() - Date.now();
            if (remaining <= 0) {
                // Expired — next sync will clear it
                return;
            }
            paymentTimerSeconds = Math.ceil(remaining / 1000);
            showPaymentBanner(pp.amount, paymentTimerSeconds);
            showRetryButton(pp.payment_url);
            pollPaymentStatus(pp.order_id);
            paymentTimerInterval = setInterval(tickPaymentTimer, 1000);
            try {
                localStorage.setItem(PENDING_PAYMENT_KEY, JSON.stringify({
                    orderId: pp.order_id,
                    amount: pp.amount,
                    paymentUrl: pp.payment_url,
                    paymentProvider: pp.payment_provider || 'yoomoney',
                    expiresAt: new Date(pp.expires_at).getTime()
                }));
            } catch (e) {}
            return;
        }

        // Timer is running — track order id for expiry detection
        if (pp) {
            lastPendingOrderId = pp.order_id;
        }
        if (data.has_pending_payment !== undefined) {
            updatePendingBanner(data.has_pending_payment);
        }
    };

    function getStoredOrderId() {
        try {
            var s = localStorage.getItem(PENDING_PAYMENT_KEY);
            if (!s) return null;
            return JSON.parse(s).orderId;
        } catch (e) { return null; }
    }

    // Restore timer immediately from localStorage, sync will verify/correct via server
    checkPendingPaymentOnLoad();

    // Initial DOM formatting for statically rendered elements
    document.querySelectorAll('.format-date').forEach(el => {
        if (el.dataset.date) {
            el.textContent = formatExpireDate(el.dataset.date);
        }
    });

    const trafficTextEl = document.getElementById('wl-traffic-text');
    const trafficProgressEl = document.getElementById('wl-traffic-progress');
    if (trafficTextEl && trafficTextEl.dataset.limit) {
        const wlLimit = parseInt(trafficTextEl.dataset.limit) || 0;
        const wlUsed = parseInt(trafficTextEl.dataset.used) || 0;
        const remaining = Math.max(0, wlLimit - wlUsed);
        trafficTextEl.textContent = `${formatBytes(remaining)} / ${formatBytes(wlLimit)}`;
        
        if (trafficProgressEl && wlLimit > 0) {
            const percent = Math.min(100, Math.max(0, (wlUsed / wlLimit) * 100));
            trafficProgressEl.style.width = `${percent}%`;
            if (percent > 90) trafficProgressEl.style.background = '#F44336';
            else if (percent > 70) trafficProgressEl.style.background = '#FF9800';
            else trafficProgressEl.style.background = '#4CAF50';
        }
    }

    // Wait for auth (initTelegram sets authenticatedUserId) before the first
    // sync, so the initial sync + link prefetch always run with a known user.
    initTelegram().then(() => startDataSync());

    // Mouse drag-to-scroll for sliders
    const sliders = document.querySelectorAll('.subscription-slider');
    sliders.forEach(slider => {
        let isDown = false;
        let startX;
        let scrollLeft;

        slider.addEventListener('mousedown', (e) => {
            isDown = true;
            slider.style.scrollSnapType = 'none'; // Disable snapping while dragging
            slider.style.cursor = 'grabbing';
            startX = e.pageX - slider.offsetLeft;
            scrollLeft = slider.scrollLeft;
        });
        slider.addEventListener('mouseleave', () => {
            isDown = false;
            slider.style.scrollSnapType = 'x mandatory';
            slider.style.cursor = 'grab';
        });
        slider.addEventListener('mouseup', () => {
            isDown = false;
            slider.style.scrollSnapType = 'x mandatory';
            slider.style.cursor = 'grab';
        });
        slider.addEventListener('mousemove', (e) => {
            if (!isDown) return;
            e.preventDefault();
            const x = e.pageX - slider.offsetLeft;
            const walk = (x - startX) * 2; // scroll-fast multiplier
            slider.scrollLeft = scrollLeft - walk;
        });
    });
});

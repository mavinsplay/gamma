document.addEventListener('DOMContentLoaded', () => {
    const navItems = document.querySelectorAll('.nav-item');
    const navIndicator = document.querySelector('.nav-indicator');
    const SAFE_MOCK_USER_DATA = (typeof MOCK_USER_DATA !== 'undefined') ? MOCK_USER_DATA : null;
    const views = document.querySelectorAll('.view');
    const pageTitle = document.getElementById('page-title');
    const pillNavItems = document.querySelectorAll('.nav-pill .nav-item');
    window.authenticatedUserId = null;

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
        if (window.authenticatedUserId && typeof ADMIN_ID !== 'undefined' && String(window.authenticatedUserId) === String(ADMIN_ID)) {
            const adminLink = document.getElementById('admin-panel-link');
            if (adminLink) adminLink.style.display = 'flex';
        }
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

    let lastModalTime = 0;
    let modalKeepOpen = false;

    function showModal({ title, message, icon = 'info', actionText = 'Пополнить', onAction = null, showInput = false, inputValue = '', inputPlaceholder = 'Введите данные...', inputType = 'text', customHtml = '', closeBtnText = 'Закрыть' }) {
        lastModalTime = Date.now();
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
            modalAction.onclick = () => {
                modalKeepOpen = false;
                const currentModalTime = lastModalTime = Date.now();
                onAction();
                // Only hide if no other modal was opened during onAction
                // and the action didn't request to stay open (e.g. debug mode).
                if (!modalKeepOpen && lastModalTime === currentModalTime) {
                    hideModal();
                }
            };
        } else {
            modalAction.style.display = 'none';
        }

        modalOverlay.classList.add('active');
    }

    function hideModal() {
        modalOverlay.classList.remove('active');
        modalClose.textContent = 'Закрыть';
        // Clean up extra buttons if any
        document.querySelectorAll('.test-topup-extra').forEach(el => el.remove());
    }

    modalClose.onclick = () => { if (!modalKeepOpen) hideModal(); };
    modalOverlay.onclick = (e) => {
        if (e.target === modalOverlay && !modalKeepOpen) hideModal();
    };

    function showPaymentMethodPicker(amount) {
        let selectedMethod = 'yoomoney';
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
                        <div class="payment-method-desc">Система быстрых платежей (Platega)</div>
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
                        <div class="payment-method-desc">USDT, TON, TRX и др. (Platega)</div>
                    </div>
                    <div class="payment-method-check">✓</div>
                </div>
            </div>
        `;
        showModal({
            title: 'Способ оплаты',
            message: `Сумма: ${amount} ₽. Выберите метод оплаты:`,
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
                };
            });
        }, 50);
    }

    window.handleTopup = (initialAmount = '') => {
        const message = initialAmount
            ? `На вашем счёте недостаточно ${initialAmount} ₽. Введите сумму для пополнения:`
            : 'Введите сумму, на которую вы хотите пополнить счёт:';
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

    const PENDING_PAYMENT_KEY = 'gamma_pending_payment';
    let paymentTimerInterval = null;
    let paymentTimerSeconds = 0;

    function startPaymentTimer(orderId, amount, paymentUrl, expiresAt) {
        if (!expiresAt) {
            expiresAt = Date.now() + 10 * 60 * 1000;
        }
        try {
            localStorage.setItem(PENDING_PAYMENT_KEY, JSON.stringify({
                orderId: orderId,
                amount: amount,
                paymentUrl: paymentUrl,
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
                    const balanceAmount = document.getElementById('profile-balance');
                    if (balanceAmount && data.new_balance !== undefined) {
                        balanceAmount.textContent = `${data.new_balance.toFixed(0)} ₽`;
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
                } else if (data.status === 'failed') {
                    clearInterval(paymentPollInterval);
                    paymentPollInterval = null;
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
                    startPaymentTimer(data.order_id, amount, data.payment_url, expiresAt);
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
                // Timer will be restored on next sync from server data
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
                        } else {
                            btn.textContent = 'Заменить';
                            btn.disabled = false;
                            btn.style.opacity = '1';
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
                                <button class="action-btn bounce extend-btn" style="background: rgba(76, 175, 80, 0.15); color: #4CAF50;" onclick="handleTopupWhitelistTraffic()">
                                    <span class="material-symbols-rounded">add_circle</span>+5 ГБ за 150 ₽
                                </button>
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
                        const btnGet = document.getElementById('btn-get-link');
                        if (btnGet) {
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
                            btnGet.parentNode.insertBefore(switcher, btnGet);
                        }
                    }
                }

                // Force connection view rebuild after buy by removing the button
                const oldBtn = document.getElementById('btn-get-link');
                if (oldBtn) oldBtn.remove();
                const oldResult = document.getElementById('connection-result');
                if (oldResult) oldResult.remove();

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
                handleTopup(Math.ceil(data.missing_amount));
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
            const remainingDays = window.REMAINING_DAYS || 0;
            const currentName = window.CURRENT_TARIFF_NAME || 'Текущий тариф';

            const comparisonHtml = `
                <div style="width:100%;text-align:left;display:flex;flex-direction:column;gap:10px;">
                    <div style="background:rgba(255,255,255,0.05);border-radius:14px;padding:12px 14px;">
                        <div style="font-size:10px;color:var(--md-sys-color-primary);opacity:.8;text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;">Текущий тариф</div>
                        <div style="font-size:15px;font-weight:500;color:#E6E1E5;">${currentName}</div>
                        <div style="font-size:12px;color:rgba(230,225,229,.55);margin-top:3px;">Осталось: <b style="color:rgba(230,225,229,.85);">${remainingDays} дней</b></div>
                    </div>
                    <div style="display:flex;justify-content:center;">
                        <span class="material-symbols-rounded" style="color:var(--md-sys-color-primary);opacity:.5;font-size:20px;">arrow_downward</span>
                    </div>
                    <div style="background:rgba(208,188,255,.08);border:1px solid rgba(208,188,255,.18);border-radius:14px;padding:12px 14px;">
                        <div style="font-size:10px;color:var(--md-sys-color-primary);opacity:.8;text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;">Новый тариф</div>
                        <div style="font-size:15px;font-weight:500;color:#E6E1E5;">${tariffName}</div>
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
    const subSliderEl = document.getElementById('sub-slider');
    if (subSliderEl) {
        function snapToNearestSlide() {
            const slideWidth = subSliderEl.clientWidth;
            const index = Math.round(subSliderEl.scrollLeft / slideWidth);
            subSliderEl.scrollTo({
                left: slideWidth * index,
                behavior: 'smooth'
            });
            const dots = document.querySelectorAll('.sub-dot');
            dots.forEach((dot, i) => {
                if (i === index) dot.classList.add('active');
                else dot.classList.remove('active');
            });
        }

        subSliderEl.addEventListener('scroll', () => {
            const index = Math.round(subSliderEl.scrollLeft / subSliderEl.clientWidth);
            const dots = document.querySelectorAll('.sub-dot');
            dots.forEach((dot, i) => {
                if (i === index) dot.classList.add('active');
                else dot.classList.remove('active');
            });
        });

        // Drag-to-scroll for PC
        let isDragging = false;
        let didDrag = false;
        let startX, scrollLeft;

        subSliderEl.addEventListener('mousedown', (e) => {
            isDragging = true;
            didDrag = false;
            startX = e.pageX;
            scrollLeft = subSliderEl.scrollLeft;
            subSliderEl.classList.add('dragging');
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = e.pageX - startX;
            if (Math.abs(dx) > 3) didDrag = true;
            if (didDrag) {
                subSliderEl.scrollLeft = scrollLeft - dx;
            }
        });

        document.addEventListener('mouseup', () => {
            if (!isDragging) return;
            isDragging = false;
            subSliderEl.classList.remove('dragging');
            if (didDrag) {
                snapToNearestSlide();
            }
        });

        // Prevent click on children if we were dragging
        subSliderEl.addEventListener('click', (e) => {
            if (didDrag) {
                e.preventDefault();
                e.stopPropagation();
                didDrag = false;
            }
        }, true);
    }

    window.toggleExtendMenu = (subType = 'main') => {
        if (!window.CURRENT_TARIFF_PRICE || !window.CURRENT_TARIFF_DAYS) return;

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

    window.handleExtend = (months, price, subType = 'main') => {
        showModal({
            title: 'Подтверждение',
            message: `Продлить подписку на ${months} мес. за ${price} ₽? Сумма будет списана с вашего баланса.`,
            icon: 'update',
            actionText: 'Продлить',
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
                        handleTopup(Math.ceil(data.missing_amount));
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
        });
    };

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
                        handleTopup(Math.ceil(data.missing_amount));
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
        });
    };

    let currentSubLink = '';
    window.selectedSubType = 'main';

    window.switchSubType = (type) => {
        window.selectedSubType = type;
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
        // Reset QR result when switching
        const btnGet = document.getElementById('btn-get-link');
        const resultDiv = document.getElementById('connection-result');
        if (resultDiv && resultDiv.classList.contains('animate-in')) {
            resultDiv.classList.remove('animate-in');
            resultDiv.classList.add('hiding');
            setTimeout(() => {
                resultDiv.classList.remove('hiding');
                currentSubLink = '';
            }, 300);
        } else {
            currentSubLink = '';
        }
        if (btnGet) {
            btnGet.classList.remove('hiding');
        }
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

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.openLink) {
            // Inside Telegram Mini App: happ:// can't be opened directly from WebView.
            // Open our server-side redirect page in the system browser via Telegram API —
            // the system browser handles the happ:// deep link correctly.
            const redirectUrl = window.location.origin
                + '/connect/open-sub/?link='
                + encodeURIComponent(currentSubLink);
            window.Telegram.WebApp.openLink(redirectUrl, { try_instant_view: false });
        } else {
            // Regular browser: direct deep link works fine
            window.location.href = 'happ://' + currentSubLink;
        }
    };

    window.handleConnect = async () => {
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

        const subType = window.selectedSubType || 'main';
        showLoading('Получение ссылки...');
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

            if (response.ok && data.success && data.link) {
                showSuccessAnim(() => {
                    currentSubLink = data.link;
                    const btnGet = document.getElementById('btn-get-link');
                    const resultDiv = document.getElementById('connection-result');
                    const qrCanvas = document.getElementById('qr-code-canvas');

                    if (btnGet) btnGet.classList.add('hiding');
                    if (resultDiv) {
                        resultDiv.classList.remove('hiding');
                        resultDiv.classList.add('animate-in');
                        if (qrCanvas && window.QRious) {
                            new QRious({
                                element: qrCanvas,
                                value: data.link,
                                size: 160,
                                level: 'M',
                                background: 'white',
                                foreground: 'black'
                            });
                        }
                    }
                });
            } else {
                hideLoading();
                showModal({
                    title: 'Ошибка',
                    message: data.error || 'У вас нет активной подписки.',
                    icon: 'error',
                    actionText: 'Ок',
                    onAction: hideModal
                });
            }
        } catch (error) {
            console.error('handleConnect error:', error);
            hideLoading();
            showModal({
                title: 'Ошибка',
                message: 'Не удалось получить ссылку. Проверьте интернет-соединение или попробуйте позже.',
                icon: 'cloud_off',
                actionText: 'Ок',
                onAction: hideModal
            });
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

    window.handleBuySlot = async () => {
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

        showModal({
            title: 'Купить доп. слот',
            message: 'Вы уверены, что хотите купить дополнительный слот для устройства за 100 ₽?',
            icon: 'person_add',
            actionText: 'Подтвердить',
            onAction: async () => {
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
                        handleTopup(Math.ceil(data.missing_amount));
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
                        hideLoading();
                        if (window.syncNow) window.syncNow();
                        // Animate row out
                        const row = document.getElementById(`device-row-${rowIndex}`);
                        if (row) {
                            row.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                            row.style.opacity = '0';
                            row.style.transform = 'translateX(20px)';
                            // Remove adjacent divider
                            const next = row.nextElementSibling;
                            const prev = row.previousElementSibling;
                            const divider = (next && next.classList.contains('settings-divider')) ? next
                                : (prev && prev.classList.contains('settings-divider')) ? prev : null;
                            setTimeout(() => {
                                row.remove();
                                if (divider) divider.remove();
                                // If block is now empty, show empty state
                                const block = document.querySelector('#view-settings .settings-block');
                                if (block && block.querySelectorAll('.device-row').length === 0) {
                                    block.innerHTML = `
                                        <div class="settings-empty">
                                            <span class="material-symbols-rounded">devices_off</span>
                                            <span>Нет подключённых устройств</span>
                                        </div>`;
                                }
                            }, 350);
                        }
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

        // Update Balance and Profile Details
        if (data.profile) {
            const balanceEl = document.getElementById('profile-balance');
            if (balanceEl) balanceEl.textContent = `${data.profile.balance.toFixed(0)} ₽`;

            const tarifNameEl = document.getElementById('profile-tarif-name');
            if (tarifNameEl) tarifNameEl.textContent = data.profile.tarif_name;

            // Update global tariff variables for Extension menu
            if (data.profile.tarif_price) window.CURRENT_TARIFF_PRICE = data.profile.tarif_price;
            if (data.profile.tarif_days) window.CURRENT_TARIFF_DAYS = data.profile.tarif_days;

            // Update HAS_ACTIVE_SUB flag
            // Use OR with OPTIMISTIC_HAS_SUB to avoid flickering right after purchase
            // Has active sub only if both RW user exists AND DB has a real tariff (not "—")
            window.HAS_ACTIVE_SUB = (!!data.rw_user && data.profile.tarif_price > 0) || !!window.OPTIMISTIC_HAS_SUB;
            if (data.rw_user) {
                window.CURRENT_TARIFF_NAME = data.profile.tarif_name;
                window.OPTIMISTIC_HAS_SUB = false; // Reset once we have real data from Remnawave
            }

            // Update settings toggles
            const paymentReminderToggle = document.getElementById('toggle-payment-reminder');
            const notificationsToggle = document.getElementById('toggle-notifications');
            if (paymentReminderToggle && data.profile.payment_reminder_enabled !== undefined) {
                paymentReminderToggle.checked = data.profile.payment_reminder_enabled;
            }
            if (notificationsToggle && data.profile.notifications_enabled !== undefined) {
                notificationsToggle.checked = data.profile.notifications_enabled;
            }
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
                                    <h4 style="margin: 0; font-size: 15px; font-weight: 500; color: #FFFFFF;">${proxy.name}</h4>
                                </div>
                                <span style="font-size: 12px; opacity: 0.5; color: #E6E1E5; display: block; margin-top: 2px;">Telegram Прокси</span>
                            </div>
                        </div>
                        
                        <div style="display: flex; gap: 10px; position: relative; z-index: 1;">
                            <button class="action-btn bounce" 
                                    style="flex: 1; height: 48px; background: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary); border-radius: 14px; font-weight: 600; font-size: 14px;" 
                                    onclick="handleProxyConnect('${proxy.connection_url}', '${proxy.name}')">
                                <span class="material-symbols-rounded" style="font-size: 20px;">bolt</span>
                                Подключить
                            </button>
                            <button class="action-btn bounce" 
                                    style="width: 48px; height: 48px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; display: flex; align-items: center; justify-content: center; padding: 0;" 
                                    onclick="copyProxyLink('${proxy.connection_url}')"
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
            if (data.rw_user && data.profile) {
                const remDays = data.rw_user.remaining_days || 0;
                
                // Format dates in slider
                document.querySelectorAll('.format-date').forEach(el => {
                    if (el.dataset.date) {
                        el.textContent = formatExpireDate(el.dataset.date);
                    }
                });

                // Update Whitelist Slide specifically if exists
                if (data.whitelist_user) {
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
                } else {
                    // Remove whitelist slide if it exists but user no longer has one
                    const wlSlide = document.querySelector('.wl-slide');
                    if (wlSlide) {
                        wlSlide.remove();
                        // Update slider dots
                        const dotsContainer = document.getElementById('sub-slider-dots');
                        if (dotsContainer) {
                            dotsContainer.style.display = 'none';
                        }
                    }
                    window.HAS_WHITELIST_SUB = false;
                }
                
                window.REMAINING_DAYS = remDays;

                // Update status text in subscription card
                const subStatusText = document.getElementById('sub-status-text');
                const subStatusEl = subStatusText?.closest('.sub-status-minimal');
                if (subStatusText && data.rw_user) {
                    if (remDays > 0) {
                        const expireAt = data.rw_user.expireAt || data.rw_user.expire_at;
                        const expireStr = expireAt ? formatExpireDate(expireAt) : '';
                        subStatusText.innerHTML = `До <span>${expireStr}</span> &bull; ${remDays} дн.`;
                    } else {
                        subStatusText.textContent = 'Истекла';
                    }
                }
                if (subStatusEl) {
                    subStatusEl.className = 'sub-status-minimal ' + (remDays > 3 ? 'status-active' : remDays > 0 ? 'status-expiring' : 'status-expired');
                }

                // Update whitelist status text
                if (data.whitelist_user) {
                    const wlRemDays = data.whitelist_user.remaining_days || 0;
                    const wlStatusText = document.getElementById('wl-status-text');
                    const wlStatusEl = wlStatusText?.closest('.sub-status-minimal');
                    if (wlStatusText) {
                        if (wlRemDays > 0) {
                            const wlExpire = data.whitelist_user.expireAt || data.whitelist_user.expire_at;
                            const wlExpStr = wlExpire ? formatExpireDate(wlExpire) : '';
                            wlStatusText.innerHTML = `До <span>${wlExpStr}</span> &bull; ${wlRemDays} дн.`;
                        } else {
                            wlStatusText.textContent = 'Истекла';
                        }
                    }
                    if (wlStatusEl) {
                        wlStatusEl.className = 'sub-status-minimal ' + (wlRemDays > 3 ? 'status-active' : wlRemDays > 0 ? 'status-expiring' : 'status-expired');
                    }
                }

                // Update device info
                const deviceTextEl = document.getElementById('sub-device-text');
                if (deviceTextEl && data.hwid_devices && data.rw_user) {
                    const devLimit = data.rw_user.hwidDeviceLimit || 0;
                    deviceTextEl.textContent = `${data.hwid_devices.length} / ${devLimit} устройств`;
                }
            } else {
                subContainer.innerHTML = '';
            }
        }

        // Update Connection View Status
        const connectionSubInfo = document.querySelector('#view-connection .subscription-info');
        if (connectionSubInfo && data.profile) {
            const daysEl = document.getElementById('connection-remaining-days');
            const getBtn = document.getElementById('btn-get-link');
            const resultEl = document.getElementById('connection-result');

            const wasActive = !!getBtn;
            const isActive = !!data.rw_user;
            const needsRebuild = !getBtn && isActive;

            if (wasActive !== isActive || needsRebuild) {
                // Redraw everything only if status changed or button missing
                const username = document.getElementById('connection-username')?.textContent || `@${tg?.initDataUnsafe?.user?.username || SAFE_MOCK_USER_DATA?.username || 'user'}`;
                let connHtml = `
                    <div class="info-item">
                        <span class="label">Пользователь</span>
                        <span class="value" id="connection-username">${username}</span>
                    </div>`;

                if (isActive) {
                    const hasWl = !!data.whitelist_user;
                    connHtml += `
                        <div class="info-item">
                            <span class="label">Статус</span>
                            <span class="value" style="color: #4CAF50;">Активен</span>
                        </div>
                        <div class="info-item">
                            <span class="label">Осталось времени</span>
                            <span class="value" id="connection-remaining-days">${data.rw_user.remaining_days} дней</span>
                        </div>`;

                    if (hasWl) {
                        connHtml += `
                        <div id="sub-type-switcher" class="sub-type-switcher">
                            <div class="sub-type-indicator"></div>
                            <button id="sub-type-main" class="sub-type-btn active" onclick="switchSubType('main')">
                                <span class="material-symbols-rounded" style="font-size: 16px; vertical-align: middle; margin-right: 4px;">verified_user</span>Основная
                            </button>
                            <button id="sub-type-whitelist" class="sub-type-btn" onclick="switchSubType('whitelist')">
                                <span class="material-symbols-rounded" style="font-size: 16px; vertical-align: middle; margin-right: 4px;">shield_locked</span>Дополнительная
                            </button>
                        </div>`;
                    }

                    connHtml += `
                        <button id="btn-get-link" class="action-btn bounce" style="margin-top: 16px; background-color: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary);" onclick="handleConnect()">
                            <span class="material-symbols-rounded">link</span>
                            Получить ссылку для подключения
                        </button>
                        <div id="connection-result" class="connection-result" style="margin-top: 16px; flex-direction: column; align-items: center; gap: 16px; padding: 16px; background: rgba(255,255,255,0.05); border-radius: 16px;">
                            <span style="font-size: 14px; color: var(--panel-icon); text-align: center;">Отсканируйте QR-код или скопируйте ссылку для настройки клиента</span>
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
                        </div>`;
                } else {
                    connHtml += `
                        <button class="action-btn bounce" style="margin-top: 16px; opacity: 0.5;" disabled>
                            <span class="material-symbols-rounded">link_off</span>
                            Нет активной подписки
                        </button>`;
                }
                connectionSubInfo.innerHTML = connHtml;
                // Re-render QR code if a link was already fetched this session
                if (currentSubLink) {
                    const resultDiv = document.getElementById('connection-result');
                    const qrCanvas = document.getElementById('qr-code-canvas');
                    const btnGet = document.getElementById('btn-get-link');
                    if (resultDiv) {
                        resultDiv.classList.remove('hiding');
                        resultDiv.classList.add('animate-in');
                    }
                    if (btnGet) btnGet.classList.add('hiding');
                    if (qrCanvas && window.QRious) {
                        new QRious({
                            element: qrCanvas,
                            value: currentSubLink,
                            size: 160,
                            level: 'M',
                            background: 'white',
                            foreground: 'black'
                        });
                    }
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
                    } else {
                        btn.textContent = 'Купить';
                        btn.classList.remove('owned');
                        btn.disabled = false;
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
                             ${data.is_admin ? `onclick="handleSetNodeStatus('${node.id}', '${nodeJson}')"` : ''}>
                            <div class="server-info">
                                <div class="server-icon-wrapper">
                                    ${node.countryCode ? `
                                        <img src="${IS_DEBUG ? 'https://flagcdn.com/w80/' : 'https://gamma.careerpiter.ru/tg-flags/w80/'}${node.countryCode.toLowerCase()}.png" 
                                             class="flag-img" 
                                             alt="${node.countryCode}">
                                    ` : `
                                        <span class="material-symbols-rounded">
                                            ${node.isConnected ? 'lan' : 'lan_off'}
                                        </span>
                                    `}
                                </div>
                                <div class="server-details">
                                    <span class="server-name">${node.display_name}</span>
                                    <span class="server-ping">
                                        <span style="color: ${statusColor}; font-weight: 500;">${statusText}</span>
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
        if (deviceCountEl && data.rw_user) {
            deviceCountEl.innerHTML = `
                <span class="material-symbols-rounded" style="font-size: 14px;">devices</span>
                ${data.hwid_devices.length} / ${data.rw_user.hwidDeviceLimit || 0}
            `;
        }

        const devicesContainer = document.getElementById('devices-list-container');
        if (devicesContainer && data.hwid_devices) {
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
                                <span class="device-row-name">${device.deviceModel || "Неизвестное устройство"}</span>
                                <span class="device-row-meta">${device.platform || "—"} · ${device.hwid.substring(0, 14)}...</span>
                            </div>
                            <button class="device-delete-btn bounce"
                                    onclick="handleDeleteDevice('${device.hwid}', ${idx})"
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
        if (slotContainer) {
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

        // Update Payment History
        const historyContainer = document.getElementById('history-list-container');
        if (historyContainer && data.payments) {
            if (data.payments.length === 0) {
                historyContainer.innerHTML = `
                    <div style="display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 40px 20px; opacity: 0.4; text-align: center;">
                        <span class="material-symbols-rounded" style="font-size: 48px;">receipt_long</span>
                        <span>История платежей пока пуста</span>
                    </div>`;
            } else {
                let historyHtml = '';
                data.payments.forEach(payment => {
                    const isTopup = payment.order_type === 'TOPUP';
                    let statusColor = '#EF5350';
                    let statusText = 'Ошибка';
                    if (payment.status === 'PAID') {
                        statusColor = '#4CAF50';
                        statusText = 'Успешно';
                    } else if (payment.status === 'PENDING') {
                        statusColor = '#FF9F0A';
                        statusText = 'В обработке';
                    }
                    historyHtml += `
                        <div class="history-item" style="background: var(--panel-bg); border-radius: 20px; padding: 16px; display: flex; align-items: center; gap: 16px;">
                            <div style="width: 44px; height: 44px; border-radius: 14px; background: ${isTopup ? 'rgba(76, 175, 80, 0.1)' : 'rgba(255, 255, 255, 0.05)'}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                                <span class="material-symbols-rounded" style="color: ${isTopup ? '#4CAF50' : '#FFFFFF'}; font-size: 24px; opacity: 0.8;">
                                    ${isTopup ? 'account_balance_wallet' : 'shopping_bag'}
                                </span>
                            </div>
                            <div style="flex: 1;">
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2px;">
                                    <span style="font-weight: 500; font-size: 15px;">
                                        ${isTopup ? 'Пополнение баланса' : (payment.tariff_name || "Покупка тарифа")}
                                    </span>
                                    <span style="font-weight: 600; font-size: 15px; color: ${isTopup ? '#4CAF50' : '#FFFFFF'};">
                                        ${isTopup ? '+' : '-'}${payment.amount.toFixed(0)} ₽
                                    </span>
                                </div>
                                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; opacity: 0.5;">
                                    <span>${payment.created_at}</span>
                                    <span style="color: ${statusColor}; opacity: 0.8;">
                                        ${statusText}
                                    </span>
                                </div>
                            </div>
                        </div>`;
                });
                historyContainer.innerHTML = historyHtml;
            }
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
    const totalInstrSlides = 4;

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

    window.downloadHiddify = (platform) => {
        let url = 'https://happ.su/';
        if (platform === 'ios' || platform === 'mac') {
            url = 'https://apps.apple.com/us/app/happ-proxy-utility/id6504287215';
        } else if (platform === 'android') {
            url = 'https://play.google.com/store/apps/details?id=com.happproxy';
        } else if (platform === 'windows') {
            url = 'https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe';
        }

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
        if (currentInstrSlide < totalInstrSlides - 1) {
            currentInstrSlide++;
            updateInstructionCarousel();
        }
    };

    window.skipToLastSlide = () => {
        currentInstrSlide = totalInstrSlides - 1;
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

        if (track) {
            track.style.transform = `translateX(-${currentInstrSlide * 25}%)`;
        }

        if (dots) {
            dots.forEach((dot, index) => {
                dot.classList.toggle('active', index === currentInstrSlide);
            });
        }

        if (prevBtn) {
            prevBtn.style.visibility = currentInstrSlide === 0 ? 'hidden' : 'visible';
        }

        if (skipBtn) {
            skipBtn.style.display = currentInstrSlide === totalInstrSlides - 1 ? 'none' : 'block';
        }

        if (nextBtn) {
            if (currentInstrSlide === totalInstrSlides - 1) {
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
                    .then(function(result) {
                        if (result.status === 'paid') {
                            showModal({
                                title: 'Готово!',
                                message: 'Баланс пополнен.',
                                icon: 'check_circle',
                                actionText: 'Отлично',
                                onAction: function() {
                                    hideModal();
                                    if (window.syncNow) window.syncNow();
                                }
                            });
                            if (window.syncNow) window.syncNow();
                        } else {
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

    initTelegram();
    startDataSync();

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

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

    function initTelegram() {
        let user = null;

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe?.user) {
            const tg = window.Telegram.WebApp;
            tg.ready();
            tg.expand();
            user = tg.initDataUnsafe.user;
        } else if (IS_DEBUG && MOCK_USER_DATA) {
            console.log('Using mock user data for development');
            user = MOCK_USER_DATA;
        }

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

    // Modal Handling
    const modalOverlay = document.getElementById('modal-overlay');
    const modalTitle = document.getElementById('modal-title');
    const modalMessage = document.getElementById('modal-message');
    const modalIcon = document.getElementById('modal-icon-text');
    const modalClose = document.getElementById('modal-close');
    const modalAction = document.getElementById('modal-action');
    const modalInputContainer = document.getElementById('modal-input-container');
    const modalAmountInput = document.getElementById('modal-amount-input');

    function showModal({ title, message, icon = 'info', actionText = 'Пополнить', onAction = null, showInput = false, inputValue = '', customHtml = '' }) {
        modalTitle.textContent = title;
        modalMessage.textContent = message;
        modalIcon.textContent = icon;
        modalAction.textContent = actionText;

        if (showInput) {
            modalInputContainer.style.display = 'block';
            modalAmountInput.value = inputValue;
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
                onAction();
                hideModal();
            };
        } else {
            modalAction.style.display = 'none';
        }

        modalOverlay.classList.add('active');
    }

    function hideModal() {
        modalOverlay.classList.remove('active');
        // Clean up extra buttons if any
        document.querySelectorAll('.test-topup-extra').forEach(el => el.remove());
    }

    modalClose.onclick = hideModal;
    modalOverlay.onclick = (e) => {
        if (e.target === modalOverlay) hideModal();
    };

    window.handleTopup = () => {
        showModal({
            title: 'Пополнение баланса',
            message: 'Введите сумму, на которую вы хотите пополнить счёт:',
            icon: 'payments',
            actionText: 'Пополнить',
            showInput: true,
            inputValue: '',
            onAction: () => {
                const amount = parseFloat(modalAmountInput.value);
                if (isNaN(amount) || amount <= 0) {
                    alert('Пожалуйста, введите корректную сумму.');
                    return;
                }
                performTopup(amount);
            }
        });
    };

    async function performTopup(amount) {
        const tg = window.Telegram?.WebApp;
        const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id || '123456789';

        try {
            const formData = new FormData();
            formData.append('amount', amount);
            formData.append('tg_id', userId);
            formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

            const response = await fetch('/shop/topup-api/', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                const balanceAmount = document.querySelector('.balance-card .amount');
                if (balanceAmount) {
                    balanceAmount.textContent = `${data.new_balance.toFixed(2)} ₽`;
                }

                // Remove extra buttons
                document.querySelectorAll('.test-topup-extra').forEach(el => el.remove());

                showModal({
                    title: 'Готово!',
                    message: `Ваш баланс успешно пополнен на ${amount} ₽.`,
                    icon: 'check_circle',
                    actionText: 'Отлично',
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

    // Loading Animation
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');

    function showLoading(text = 'Обработка...') {
        loadingText.textContent = text;
        loadingOverlay.classList.remove('success');
        loadingOverlay.classList.add('active');
    }

    function showSuccessAnim(callback) {
        loadingOverlay.classList.add('success');
        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
        }
        setTimeout(() => {
            loadingOverlay.classList.remove('active');
            loadingOverlay.classList.remove('success');
            if (callback) callback();
        }, 1500);
    }

    function hideLoading() {
        loadingOverlay.classList.remove('active');
        loadingOverlay.classList.remove('success');
    }

    window.handleBuy = async (tariffId, price) => {
        const tg = window.Telegram?.WebApp;
        const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id; // Mock for dev
        const username = tg?.initDataUnsafe?.user?.username || MOCK_USER_DATA?.username;

        showLoading('Оформление подписки...');

        try {
            const formData = new FormData();
            formData.append('tariff_id', tariffId);
            formData.append('tg_id', userId);
            formData.append('csrfmiddlewaretoken', CSRF_TOKEN);
            formData.append('tg_username', username);

            const response = await fetch('/shop/buy-api/', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                // Update balance in UI
                const balanceAmount = document.querySelector('.balance-card .amount');
                if (balanceAmount) {
                    balanceAmount.textContent = `${data.new_balance.toFixed(2)} ₽`;
                }

                showSuccessAnim(() => {
                    // Force reload to show active subscription banner
                    window.location.reload();
                });
            } else if (data.error === 'insufficient_funds') {
                hideLoading();
                showModal({
                    title: 'Недостаточно средств',
                    message: `Для покупки этого тарифа вам не хватает ${data.missing_amount.toFixed(2)} ₽. Пополните баланс на сумму тарифа (${price} ₽) и попробуйте снова.`,
                    icon: 'account_balance_wallet',
                    actionText: `Пополнить на ${price} ₽`,
                    onAction: () => {
                        performTopup(price);
                    }
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
    };

    window.toggleExtendMenu = () => {
        if (!window.CURRENT_TARIFF_PRICE || !window.CURRENT_TARIFF_DAYS) return;
        
        const basePrice = window.CURRENT_TARIFF_PRICE;
        const baseDays = window.CURRENT_TARIFF_DAYS;
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
                <button class="extend-option bounce" onclick="window.handleExtend(${opt.months}, ${optionPrice})" style="width: 100%; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.05); border-radius: 12px; padding: 12px; display: flex; flex-direction: column; align-items: center; gap: 4px;">
                    <span class="ext-months" style="font-size: 14px; font-weight: 500; color: #E6E1E5;">${opt.label}</span>
                    <span class="ext-price" style="font-size: 13px; color: var(--md-sys-color-primary); font-weight: 600;">${optionPrice} ₽</span>
                </button>
            `;
        });
        gridHtml += '</div>';

        showModal({
            title: 'Продление подписки',
            message: 'Выберите срок продления:',
            icon: 'update',
            customHtml: gridHtml,
            actionText: 'Отмена',
            onAction: null // Only close button needed, or action button as Cancel
        });
    };

    window.handleExtend = (months, price) => {
        showModal({
            title: 'Продление подписки',
            message: `Вы уверены, что хотите продлить подписку на ${months} мес. за ${price} ₽? Сумма будет списана с вашего баланса.`,
            icon: 'update',
            actionText: 'Продлить',
            onAction: async () => {
                hideModal();
                showLoading('Продление подписки...');
                const tg = window.Telegram?.WebApp;
                const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id;

                try {
                    const formData = new FormData();
                    formData.append('tg_id', userId);
                    formData.append('months', months);
                    formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

                    const response = await fetch('/shop/extend-sub-api/', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok && data.success) {
                        showSuccessAnim(() => {
                            const balanceAmount = document.querySelector('.balance-card .amount');
                            if (balanceAmount) {
                                balanceAmount.textContent = `${data.new_balance.toFixed(2)} ₽`;
                            }
                            showModal({
                                title: 'Успешно!',
                                message: `Подписка продлена на ${months} мес.`,
                                icon: 'check_circle',
                                actionText: 'Ок',
                                onAction: () => location.reload()
                            });
                        });
                    } else if (data.error === 'insufficient_funds') {
                        hideLoading();
                        showModal({
                            title: 'Недостаточно средств',
                            message: `Для продления вам не хватает ${data.missing_amount.toFixed(2)} ₽. Пополните баланс и попробуйте снова.`,
                            icon: 'account_balance_wallet',
                            actionText: `Пополнить на ${price} ₽`,
                            onAction: () => performTopup(price)
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
        });
    };

    let currentSubLink = '';

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
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.openLink(currentSubLink);
        } else {
            window.open(currentSubLink, '_blank');
        }
    };

    window.handleConnect = async () => {
        const tg = window.Telegram?.WebApp;
        const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id;

        showLoading('Получение ссылки...');
        try {
            const response = await fetch(`/shop/get-sub-link-api/?tg_id=${userId}`);
            const data = await response.json();

            if (response.ok && data.success && data.link) {
                showSuccessAnim(() => {
                    currentSubLink = data.link;
                    const btnGet = document.getElementById('btn-get-link');
                    const resultDiv = document.getElementById('connection-result');
                    const qrImg = document.getElementById('qr-code-img');
                    
                    if (btnGet) btnGet.style.display = 'none';
                    if (resultDiv) {
                        resultDiv.style.display = 'flex';
                        qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(data.link)}`;
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
            hideLoading();
            showModal({
                title: 'Ошибка',
                message: 'Не удалось получить ссылку.',
                icon: 'cloud_off',
                actionText: 'Ок',
                onAction: hideModal
            });
        }
    };

    window.handleBuySlot = async () => {
        const tg = window.Telegram?.WebApp;
        const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id;

        showModal({
            title: 'Купить доп. слот',
            message: 'Вы уверены, что хотите купить дополнительный слот для устройства за 100 ₽?',
            icon: 'person_add',
            actionText: 'Подтвердить',
            onAction: async () => {
                showLoading('Покупка слота...');
                try {
                    const formData = new FormData();
                    formData.append('tg_id', userId);
                    formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

                    const response = await fetch('/shop/buy-slot-api/', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok) {
                        const balanceAmount = document.querySelector('.balance-card .amount');
                        if (balanceAmount) {
                            balanceAmount.textContent = `${data.new_balance.toFixed(2)} ₽`;
                        }
                        showSuccessAnim(() => {
                            window.location.reload();
                        });
                    } else if (data.error === 'insufficient_funds') {
                        hideLoading();
                        showModal({
                            title: 'Недостаточно средств',
                            message: `Вам не хватает ${data.missing_amount.toFixed(2)} ₽.`,
                            icon: 'account_balance_wallet',
                            actionText: `Пополнить`,
                            onAction: () => {
                                handleTopup();
                            }
                        });
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
                } catch(e) {
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
});

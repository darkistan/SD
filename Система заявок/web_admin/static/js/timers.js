/**
 * Модуль для управління таймерами
 * Оновлення відбувається на клієнті без AJAX запитів
 */

(function() {
    'use strict';
    
    let timers = [];
    let updateInterval = null;
    
    /**
     * Ініціалізація таймерів
     */
    function initTimers() {
        // Збираємо всі таймери зі сторінки
        const timerCards = document.querySelectorAll('.timer-card');
        timers = [];
        
        timerCards.forEach(card => {
            const timerData = {
                id: parseInt(card.dataset.timerId),
                type: card.dataset.timerType,
                startDatetime: new Date(card.dataset.startDatetime),
                targetDatetime: card.dataset.targetDatetime ? new Date(card.dataset.targetDatetime) : null,
                isPaused: card.dataset.isPaused === 'true',
                pausedDuration: parseInt(card.dataset.pausedDuration) || 0,
                lastPauseStart: card.dataset.lastPauseStart ? new Date(card.dataset.lastPauseStart) : null,
                card: card
            };
            timers.push(timerData);
        });
        
        // Запускаємо оновлення
        if (timers.length > 0 && !updateInterval) {
            updateInterval = setInterval(updateAllTimers, 1000);
        }
        
        // Обробка кнопок управління
        setupControlButtons();
    }
    
    /**
     * Оновлення всіх таймерів
     */
    function updateAllTimers() {
        timers.forEach(timer => {
            if (!timer.isPaused || timer.lastPauseStart) {
                updateTimerDisplay(timer);
            }
        });
    }
    
    /**
     * Оновлення відображення одного таймера
     */
    function updateTimerDisplay(timer) {
        const now = new Date();
        let seconds = 0;
        
        if (timer.type === 'FORWARD') {
            // Прямий таймер: скільки часу пройшло
            const elapsed = Math.floor((now - timer.startDatetime) / 1000);
            let pausedTime = timer.pausedDuration;
            
            // Якщо таймер на паузі, додаємо час поточної паузи
            if (timer.isPaused && timer.lastPauseStart) {
                pausedTime += Math.floor((now - timer.lastPauseStart) / 1000);
            }
            
            seconds = Math.max(0, elapsed - pausedTime);
        } else {
            // Зворотний таймер: скільки часу залишилось
            if (!timer.targetDatetime) return;
            
            const remaining = Math.floor((timer.targetDatetime - now) / 1000);
            let pausedTime = timer.pausedDuration;
            
            // Якщо таймер на паузі, додаємо час поточної паузи
            if (timer.isPaused && timer.lastPauseStart) {
                pausedTime += Math.floor((now - timer.lastPauseStart) / 1000);
            }
            
            seconds = Math.max(0, remaining - pausedTime);
        }
        
        // Розраховуємо дні та години
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        
        // Оновлюємо відображення
        const daysElement = timer.card.querySelector('.timer-days');
        const hoursElement = timer.card.querySelector('.timer-hours');
        
        if (daysElement) {
            daysElement.textContent = days;
        }
        if (hoursElement) {
            hoursElement.textContent = hours;
        }
        
        // Змінюємо колір для зворотного таймера при малому залишку
        if (timer.type === 'BACKWARD' && days === 0 && hours < 24) {
            timer.card.classList.add('timer-urgent');
        } else {
            timer.card.classList.remove('timer-urgent');
        }
    }
    
    /**
     * Налаштування кнопок управління
     */
    function setupControlButtons() {
        // Кнопка паузи
        document.querySelectorAll('.timer-pause-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const timerId = parseInt(this.dataset.timerId);
                pauseTimer(timerId);
            });
        });
        
        // Кнопка продовження
        document.querySelectorAll('.timer-resume-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const timerId = parseInt(this.dataset.timerId);
                resumeTimer(timerId);
            });
        });
        
        // Кнопка скидання
        document.querySelectorAll('.timer-reset-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const timerId = parseInt(this.dataset.timerId);
                if (confirm('Скинути таймер в нуль?')) {
                    resetTimer(timerId);
                }
            });
        });
        
        // Кнопка видалення
        document.querySelectorAll('.timer-delete-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const timerId = parseInt(this.dataset.timerId);
                if (confirm('Видалити таймер?')) {
                    deleteTimer(timerId);
                }
            });
        });
    }
    
    /**
     * Зупинка таймера
     */
    function pauseTimer(timerId) {
        fetch(`/timer/${timerId}/pause`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Оновлюємо локальні дані таймера
                const timer = timers.find(t => t.id === timerId);
                if (timer) {
                    timer.isPaused = true;
                    timer.lastPauseStart = new Date();
                    // Оновлюємо атрибути картки
                    timer.card.dataset.isPaused = 'true';
                    timer.card.dataset.lastPauseStart = timer.lastPauseStart.toISOString();
                }
                // Перезавантажуємо сторінку для оновлення UI
                location.reload();
            } else {
                alert('Помилка: ' + (data.message || 'Невідома помилка'));
            }
        })
        .catch(error => {
            console.error('Помилка зупинки таймера:', error);
            alert('Помилка зупинки таймера');
        });
    }
    
    /**
     * Продовження таймера
     */
    function resumeTimer(timerId) {
        fetch(`/timer/${timerId}/resume`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.timer) {
                // Оновлюємо локальні дані таймера
                const timer = timers.find(t => t.id === timerId);
                if (timer) {
                    timer.isPaused = false;
                    timer.pausedDuration = data.timer.paused_duration || 0;
                    timer.lastPauseStart = null;
                    // Оновлюємо атрибути картки
                    timer.card.dataset.isPaused = 'false';
                    timer.card.dataset.pausedDuration = timer.pausedDuration;
                    timer.card.dataset.lastPauseStart = '';
                }
                // Перезавантажуємо сторінку для оновлення UI
                location.reload();
            } else {
                alert('Помилка: ' + (data.message || 'Невідома помилка'));
            }
        })
        .catch(error => {
            console.error('Помилка продовження таймера:', error);
            alert('Помилка продовження таймера');
        });
    }
    
    /**
     * Скидання таймера
     */
    function resetTimer(timerId) {
        fetch(`/timer/${timerId}/reset`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.timer) {
                // Оновлюємо локальні дані таймера
                const timer = timers.find(t => t.id === timerId);
                if (timer) {
                    timer.startDatetime = new Date(data.timer.start_datetime);
                    timer.isPaused = false;
                    timer.pausedDuration = 0;
                    timer.lastPauseStart = null;
                    // Оновлюємо атрибути картки
                    timer.card.dataset.startDatetime = timer.startDatetime.toISOString();
                    timer.card.dataset.isPaused = 'false';
                    timer.card.dataset.pausedDuration = '0';
                    timer.card.dataset.lastPauseStart = '';
                }
                // Оновлюємо відображення
                updateTimerDisplay(timer);
            } else {
                alert('Помилка: ' + (data.message || 'Невідома помилка'));
            }
        })
        .catch(error => {
            console.error('Помилка скидання таймера:', error);
            alert('Помилка скидання таймера');
        });
    }
    
    /**
     * Видалення таймера
     */
    function deleteTimer(timerId) {
        fetch(`/timer/${timerId}/delete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({})
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.message || 'Помилка видалення таймера');
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Спочатку знаходимо картку в DOM
                const card = document.querySelector(`.timer-card[data-timer-id="${timerId}"]`);
                if (card) {
                    card.remove();
                }
                
                // Видаляємо таймер зі списку
                timers = timers.filter(t => t.id !== timerId);
                
                // Якщо таймерів не залишилось, зупиняємо інтервал
                if (timers.length === 0 && updateInterval) {
                    clearInterval(updateInterval);
                    updateInterval = null;
                }
                
                // Перезавантажуємо сторінку для оновлення UI
                location.reload();
            } else {
                alert('Помилка: ' + (data.message || 'Невідома помилка'));
            }
        })
        .catch(error => {
            console.error('Помилка видалення таймера:', error);
            alert('Помилка видалення таймера: ' + error.message);
        });
    }
    
    // Ініціалізація при завантаженні сторінки
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTimers);
    } else {
        initTimers();
    }
    
})();

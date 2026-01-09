// TO DO Module JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Вибір всіх завдань
    const selectAllCheckbox = document.getElementById('selectAll');
    const taskSelectCheckboxes = document.querySelectorAll('.task-select');
    const bulkActionsPanel = document.getElementById('bulkActionsPanel');
    const selectedCountSpan = document.getElementById('selectedCount');
    
    // Панель деталей
    const detailsPanel = document.getElementById('detailsPanel');
    const closeDetailsBtn = document.getElementById('closeDetails');
    const taskDetailForm = document.getElementById('taskDetailForm');
    const deleteTaskBtn = document.getElementById('deleteTaskBtn');
    
    // Оновлення кількості вибраних завдань
    function updateSelectedCount() {
        const selected = document.querySelectorAll('.task-select:checked');
        const count = selected.length;
        selectedCountSpan.textContent = count;
        
        if (count > 0) {
            bulkActionsPanel.style.display = 'block';
            // Додаємо вибрані ID до форми
            const form = document.getElementById('bulkActionForm');
            form.querySelectorAll('input[name="task_ids"]').forEach(input => input.remove());
            selected.forEach(checkbox => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'task_ids';
                input.value = checkbox.value;
                form.appendChild(input);
            });
        } else {
            bulkActionsPanel.style.display = 'none';
        }
    }
    
    // Вибір всіх
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            taskSelectCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            updateSelectedCount();
        });
    }
    
    // Вибір окремих завдань
    taskSelectCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateSelectedCount();
            // Скидаємо "вибрати всі", якщо не всі вибрані
            if (selectAllCheckbox) {
                const allChecked = Array.from(taskSelectCheckboxes).every(cb => cb.checked);
                selectAllCheckbox.checked = allChecked;
            }
        });
    });
    
    // Виконання завдання
    document.querySelectorAll('.task-complete').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const taskId = this.dataset.taskId;
            if (!taskId) return;
            
            const isCompleted = this.checked;
            const action = isCompleted ? 'позначити як виконане' : 'скасувати виконання';
            
            if (!confirm(`Ви впевнені, що хочете ${action} це завдання?`)) {
                // Відміняємо зміну, якщо користувач скасував
                this.checked = !isCompleted;
                return;
            }
            
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/todo/task/${taskId}/complete`;
            
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token';
            csrfInput.value = csrfToken;
            form.appendChild(csrfInput);
            
            document.body.appendChild(form);
            form.submit();
        });
    });
    
    // Відкриття панелі деталей
    document.querySelectorAll('.task-title-link, .task-detail-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const taskId = this.dataset.taskId;
            if (!taskId) return;
            
            // Завантажуємо дані завдання
            fetch(`/todo/task/${taskId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert('Помилка завантаження завдання: ' + data.error);
                        return;
                    }
                    
                    // Заповнюємо форму
                    document.getElementById('taskId').value = data.id;
                    document.getElementById('taskTitle').value = data.title || '';
                    document.getElementById('taskNotes').value = data.notes || '';
                    
                    if (data.due_date) {
                        // Конвертуємо дату для date input (тільки дата, без часу)
                        const date = new Date(data.due_date);
                        const year = date.getFullYear();
                        const month = String(date.getMonth() + 1).padStart(2, '0');
                        const day = String(date.getDate()).padStart(2, '0');
                        document.getElementById('taskDueDate').value = `${year}-${month}-${day}`;
                    } else {
                        document.getElementById('taskDueDate').value = '';
                    }
                    
                    document.getElementById('taskRecurrence').value = data.recurrence_type || '';
                    document.getElementById('taskListName').value = data.list_name || '';
                    
                    // Оновлюємо action форми
                    taskDetailForm.action = `/todo/task/${taskId}/update`;
                    
                    // Показуємо панель
                    detailsPanel.classList.add('active');
                })
                .catch(error => {
                    console.error('Помилка:', error);
                    alert('Помилка завантаження завдання');
                });
        });
    });
    
    // Закриття панелі деталей
    if (closeDetailsBtn) {
        closeDetailsBtn.addEventListener('click', function() {
            detailsPanel.classList.remove('active');
        });
    }
    
    // Видалення завдання
    if (deleteTaskBtn) {
        deleteTaskBtn.addEventListener('click', function() {
            const taskId = document.getElementById('taskId').value;
            if (!taskId) return;
            
            if (!confirm('Ви впевнені, що хочете видалити це завдання?')) {
                return;
            }
            
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/todo/task/${taskId}/delete`;
            
            const csrfToken = document.querySelector('input[name="csrf_token"]').value;
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token';
            csrfInput.value = csrfToken;
            form.appendChild(csrfInput);
            
            document.body.appendChild(form);
            form.submit();
        });
    }
    
    // Сортування тепер відбувається на сервері, клієнтське сортування видалено
    
    // Підтвердження видалення списку
    document.querySelectorAll('.delete-list-form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const listName = this.dataset.listName || this.querySelector('input[name="list_name"]').value;
            if (!confirm(`Ви впевнені, що хочете видалити список "${listName}"?\n\nВсі завдання в цьому списку будуть без списку.`)) {
                e.preventDefault();
                return false;
            }
        });
    });
    
    
    // Показ/приховування полів дат для кастомного періоду
    const periodSelect = document.getElementById('periodSelect');
    const dateFromGroup = document.getElementById('dateFromGroup');
    const dateToGroup = document.getElementById('dateToGroup');
    
    if (periodSelect && dateFromGroup && dateToGroup) {
        periodSelect.addEventListener('change', function() {
            if (this.value === 'custom') {
                dateFromGroup.style.display = 'block';
                dateToGroup.style.display = 'block';
            } else {
                dateFromGroup.style.display = 'none';
                dateToGroup.style.display = 'none';
            }
        });
    }
    
    // Ініціалізація
    updateSelectedCount();
});

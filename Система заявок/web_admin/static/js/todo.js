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
        const selected = document.querySelectorAll('.task-select:checked, .undefined-task-select:checked');
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
    
    // Вибір всіх в групах задач
    document.querySelectorAll('.task-group-select-all').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const group = this.dataset.group;
            const groupTable = this.closest('.task-group').querySelector('table');
            if (groupTable) {
                const groupCheckboxes = groupTable.querySelectorAll('.task-select');
                groupCheckboxes.forEach(cb => {
                    cb.checked = this.checked;
                });
            }
            updateSelectedCount();
        });
    });
    
    // Вибір всіх невизначених задач
    const undefinedSelectAll = document.querySelector('.undefined-select-all');
    const undefinedTaskSelects = document.querySelectorAll('.undefined-task-select');
    if (undefinedSelectAll) {
        undefinedSelectAll.addEventListener('change', function() {
            undefinedTaskSelects.forEach(checkbox => {
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
    
    // Вибір окремих невизначених задач
    undefinedTaskSelects.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateSelectedCount();
            // Скидаємо "вибрати всі", якщо не всі вибрані
            if (undefinedSelectAll) {
                const allChecked = Array.from(undefinedTaskSelects).every(cb => cb.checked);
                undefinedSelectAll.checked = allChecked;
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
                    
                    // Зберігаємо параметри фільтрації для redirect після оновлення
                    const urlParams = new URLSearchParams(window.location.search);
                    const filterType = urlParams.get('filter') || 'all';
                    const search = urlParams.get('search') || '';
                    const listName = urlParams.get('list') || '';
                    const selectedList = urlParams.get('list_filter') || '';
                    const selectedStatus = urlParams.get('status_filter') || '';
                    const selectedImportant = urlParams.get('important_filter') || '';
                    const selectedRecurrence = urlParams.get('recurrence_filter') || '';
                    const selectedPeriod = urlParams.get('period') || '';
                    const dateFrom = urlParams.get('date_from') || '';
                    const dateTo = urlParams.get('date_to') || '';
                    const sortBy = urlParams.get('sort_by') || 'due_date';
                    const sortOrder = urlParams.get('sort_order') || 'asc';
                    
                    // Видаляємо старі приховані поля фільтрації
                    taskDetailForm.querySelectorAll('input[name^="filter_"]').forEach(input => input.remove());
                    
                    // Додаємо нові приховані поля з параметрами фільтрації
                    const addHiddenField = (name, value) => {
                        if (value) {
                            const input = document.createElement('input');
                            input.type = 'hidden';
                            input.name = name;
                            input.value = value;
                            taskDetailForm.appendChild(input);
                        }
                    };
                    
                    addHiddenField('filter_type', filterType);
                    addHiddenField('filter_search', search);
                    addHiddenField('filter_list', listName);
                    addHiddenField('filter_list_filter', selectedList);
                    addHiddenField('filter_status_filter', selectedStatus);
                    addHiddenField('filter_important_filter', selectedImportant);
                    addHiddenField('filter_recurrence_filter', selectedRecurrence);
                    addHiddenField('filter_period', selectedPeriod);
                    addHiddenField('filter_date_from', dateFrom);
                    addHiddenField('filter_date_to', dateTo);
                    addHiddenField('filter_sort_by', sortBy);
                    addHiddenField('filter_sort_order', sortOrder);
                    
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
    
    // Згортання/розгортання секцій
    document.querySelectorAll('.collapse-toggle').forEach(button => {
        const targetId = button.dataset.target;
        const target = document.getElementById(targetId);
        if (!target) return;
        
        // Встановлюємо початковий стан (згорнуто за замовчуванням)
        if (!target.classList.contains('show')) {
            button.setAttribute('aria-expanded', 'false');
        }
        
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const isExpanded = this.getAttribute('aria-expanded') === 'true';
            
            if (isExpanded) {
                // Згортаємо
                target.classList.remove('show');
                this.setAttribute('aria-expanded', 'false');
            } else {
                // Розгортаємо
                target.classList.add('show');
                this.setAttribute('aria-expanded', 'true');
            }
        });
    });
    
    // Ініціалізація
    updateSelectedCount();
});

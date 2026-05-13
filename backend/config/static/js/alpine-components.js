// static/js/alpine-components.js

document.addEventListener('alpine:init', () => {
    
    // ============================================
    // 1. EXAM RESULTS UPLOAD MANAGER
    // ============================================
    Alpine.data('examUploadManager', () => ({
        selectedExam: null,
        uploadFile: null,
        previewData: [],
        isUploading: false,
        uploadProgress: 0,
        offlineQueue: [],
        searchTerm: '',
        
        init() {
            this.loadOfflineQueue();
            this.setupEventListeners();
        },
        
        loadOfflineQueue() {
            const saved = localStorage.getItem('offlineUploads');
            if (saved) {
                this.offlineQueue = JSON.parse(saved);
            }
        },
        
        setupEventListeners() {
            window.addEventListener('online', () => {
                this.syncOfflineData();
            });
        },
        
        handleFileSelect(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            this.uploadFile = file;
            
            // Preview CSV
            if (file.name.endsWith('.csv')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const text = e.target.result;
                    const lines = text.split('\n').slice(0, 6);
                    const headers = lines[0].split(',');
                    
                    this.previewData = lines.slice(1).map(line => {
                        const values = line.split(',');
                        const row = {};
                        headers.forEach((header, i) => {
                            row[header.trim()] = values[i]?.trim() || '';
                        });
                        return row;
                    }).filter(row => Object.values(row).some(v => v));
                };
                reader.readAsText(file);
            }
            
            // Preview Excel (if SheetJS is loaded)
            else if (window.XLSX && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const data = new Uint8Array(e.target.result);
                    const workbook = XLSX.read(data, { type: 'array' });
                    const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                    const jsonData = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
                    
                    const headers = jsonData[0];
                    this.previewData = jsonData.slice(1, 6).map(row => {
                        const rowObj = {};
                        headers.forEach((header, i) => {
                            rowObj[header] = row[i] || '';
                        });
                        return rowObj;
                    });
                };
                reader.readAsArrayBuffer(file);
            }
        },
        
        async uploadResults() {
            if (!this.selectedExam || !this.uploadFile) {
                alert('Please select an exam and file');
                return;
            }
            
            this.isUploading = true;
            this.uploadProgress = 0;
            
            const formData = new FormData();
            formData.append('exam_id', this.selectedExam);
            formData.append('file', this.uploadFile);
            
            // Simulate progress
            const progressInterval = setInterval(() => {
                if (this.uploadProgress < 90) {
                    this.uploadProgress += 10;
                }
            }, 200);
            
            try {
                const response = await fetch('/exams/upload-results/', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': this.getCookie('csrftoken')
                    }
                });
                
                clearInterval(progressInterval);
                
                if (response.ok) {
                    this.uploadProgress = 100;
                    const result = await response.json();
                    this.showNotification(`Successfully uploaded ${result.count} results!`, 'success');
                    setTimeout(() => {
                        this.resetForm();
                        // Refresh the list
                        if (window.htmx) {
                            htmx.trigger('#recent-uploads', 'refresh');
                        }
                    }, 1000);
                } else {
                    throw new Error('Upload failed');
                }
            } catch (error) {
                clearInterval(progressInterval);
                this.uploadProgress = 0;
                this.saveOffline(formData);
                this.showNotification('Upload failed. Saved offline.', 'warning');
            } finally {
                setTimeout(() => {
                    this.isUploading = false;
                }, 1000);
            }
        },
        
        saveOffline(formData) {
            const data = {};
            formData.forEach((value, key) => {
                if (value instanceof File) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        data[key] = {
                            name: value.name,
                            type: value.type,
                            content: e.target.result
                        };
                        
                        this.offlineQueue.push({
                            id: Date.now(),
                            data: data,
                            timestamp: new Date().toISOString()
                        });
                        
                        localStorage.setItem('offlineUploads', JSON.stringify(this.offlineQueue));
                        this.showNotification('Saved for offline sync', 'info');
                    };
                    reader.readAsDataURL(value);
                } else {
                    data[key] = value;
                }
            });
        },
        
        async syncOfflineData() {
            if (this.offlineQueue.length === 0) return;
            
            this.showNotification(`Syncing ${this.offlineQueue.length} items...`, 'info');
            
            const successful = [];
            
            for (const item of this.offlineQueue) {
                try {
                    const formData = new FormData();
                    for (const [key, value] of Object.entries(item.data)) {
                        if (value.content) {
                            // Convert base64 back to file
                            const response = await fetch(value.content);
                            const blob = await response.blob();
                            const file = new File([blob], value.name, { type: value.type });
                            formData.append(key, file);
                        } else {
                            formData.append(key, value);
                        }
                    }
                    
                    const response = await fetch('/exams/upload-results/', {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-CSRFToken': this.getCookie('csrftoken')
                        }
                    });
                    
                    if (response.ok) {
                        successful.push(item.id);
                    }
                } catch (error) {
                    console.error('Sync failed:', error);
                }
            }
            
            // Remove successful items
            this.offlineQueue = this.offlineQueue.filter(item => !successful.includes(item.id));
            localStorage.setItem('offlineUploads', JSON.stringify(this.offlineQueue));
            
            this.showNotification(`Synced ${successful.length} items!`, 'success');
        },
        
        resetForm() {
            this.selectedExam = null;
            this.uploadFile = null;
            this.previewData = [];
            this.uploadProgress = 0;
            document.getElementById('file-upload').value = '';
        },
        
        showNotification(message, type) {
            // You can use your existing notification system
            alert(message); // Replace with your toast/notification component
        },
        
        getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
    }));
    
    // ============================================
    // 2. SCHOOL SETTINGS MANAGER
    // ============================================
    Alpine.data('schoolSettings', () => ({
        settings: {
            name: '',
            code: '',
            email: '',
            phone: '',
            address: '',
            primary_color: '#3B82F6',
            secondary_color: '#1E40AF',
            timezone: 'UTC',
            currency: 'USD',
            logo: null
        },
        isLoading: false,
        logoPreview: null,
        
        init() {
            this.loadSettings();
        },
        
        async loadSettings() {
            this.isLoading = true;
            try {
                const response = await fetch('/api/schools/settings/');
                if (response.ok) {
                    const data = await response.json();
                    this.settings = { ...this.settings, ...data };
                    if (data.logo) {
                        this.logoPreview = data.logo;
                    }
                }
            } catch (error) {
                console.error('Failed to load settings:', error);
            } finally {
                this.isLoading = false;
            }
        },
        
        handleLogoUpload(event) {
            const file = event.target.files[0];
            if (file) {
                this.settings.logo = file;
                
                const reader = new FileReader();
                reader.onload = (e) => {
                    this.logoPreview = e.target.result;
                };
                reader.readAsDataURL(file);
            }
        },
        
        async saveSettings() {
            this.isLoading = true;
            
            const formData = new FormData();
            for (const [key, value] of Object.entries(this.settings)) {
                if (value !== null && value !== undefined) {
                    formData.append(key, value);
                }
            }
            
            try {
                const response = await fetch('/api/schools/settings/', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': this.getCookie('csrftoken')
                    }
                });
                
                if (response.ok) {
                    // Update CSS variables
                    document.documentElement.style.setProperty('--primary-color', this.settings.primary_color);
                    document.documentElement.style.setProperty('--secondary-color', this.settings.secondary_color);
                    
                    this.showNotification('Settings saved successfully!', 'success');
                }
            } catch (error) {
                console.error('Failed to save settings:', error);
                this.showNotification('Failed to save settings', 'error');
            } finally {
                this.isLoading = false;
            }
        },
        
        showNotification(message, type) {
            alert(message); // Replace with your notification system
        },
        
        getCookie(name) {
            // Same as above
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
    }));
    
    // ============================================
    // 3. RESULTS FILTER & SEARCH
    // ============================================
    Alpine.data('resultsFilter', () => ({
        filters: {
            class: '',
            subject: '',
            exam: '',
            date_from: '',
            date_to: '',
            status: ''
        },
        
        applyFilters() {
            const params = new URLSearchParams();
            for (const [key, value] of Object.entries(this.filters)) {
                if (value) {
                    params.append(key, value);
                }
            }
            
            if (window.htmx) {
                htmx.ajax('GET', `/exams/results/?${params.toString()}`, {
                    target: '#results-table',
                    swap: 'innerHTML'
                });
            }
        },
        
        resetFilters() {
            this.filters = {
                class: '',
                subject: '',
                exam: '',
                date_from: '',
                date_to: '',
                status: ''
            };
            this.applyFilters();
        }
    }));
    
    // ============================================
    // 4. EXAM ATTEMPT GRADING
    // ============================================
    Alpine.data('examGrading', () => ({
        attempt: null,
        answers: [],
        currentQuestionIndex: 0,
        isSubmitting: false,
        
        init() {
            this.loadAttempt();
        },
        
        loadAttempt() {
            const attemptId = this.$el.dataset.attemptId;
            if (attemptId) {
                fetch(`/exams/attempts/${attemptId}/`)
                    .then(response => response.json())
                    .then(data => {
                        this.attempt = data.attempt;
                        this.answers = data.answers;
                    });
            }
        },
        
        nextQuestion() {
            if (this.currentQuestionIndex < this.answers.length - 1) {
                this.currentQuestionIndex++;
            }
        },
        
        prevQuestion() {
            if (this.currentQuestionIndex > 0) {
                this.currentQuestionIndex--;
            }
        },
        
        async submitGrade() {
            this.isSubmitting = true;
            
            try {
                const response = await fetch(`/exams/attempts/${this.attempt.id}/grade/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': this.getCookie('csrftoken')
                    },
                    body: JSON.stringify({ answers: this.answers })
                });
                
                if (response.ok) {
                    this.showNotification('Grades submitted successfully!', 'success');
                }
            } catch (error) {
                console.error('Failed to submit grades:', error);
                this.showNotification('Failed to submit grades', 'error');
            } finally {
                this.isSubmitting = false;
            }
        },
        
        showNotification(message, type) {
            alert(message); // Replace with your notification system
        },
        
        getCookie(name) {
            // Same as above
        }
    }));
});
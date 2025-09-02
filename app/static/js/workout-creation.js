/**
 * Améliorations JavaScript pour le flux de création de workout
 * Fichier: app/static/js/workout-creation.js
 */

// Workflow state management
const WorkoutCreation = {
    currentStep: 1,
    workoutName: '',
    exercises: [],

    // Initialize the workflow
    init: function() {
        this.bindEvents();
        this.checkLocalStorage();
        this.animateIntro();
    },

    // Bind all events
    bindEvents: function() {
        const self = this;

        // Name input monitoring
        const nameInput = document.querySelector('input[name="name"]');
        if (nameInput) {
            nameInput.addEventListener('input', function(e) {
                self.workoutName = e.target.value;
                self.updateProgress();
                self.saveToLocalStorage();
            });
        }

        // Exercise count monitoring
        this.updateExerciseCount();

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + Enter to submit
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                const form = document.getElementById('workout-form');
                if (form && self.validateForm()) {
                    form.submit();
                }
            }

            // Escape to go back
            if (e.key === 'Escape') {
                if (confirm('Weet je zeker dat je wilt stoppen met het maken van deze workout?')) {
                    window.location.href = '/index';
                }
            }
        });
    },

    // Check and restore from localStorage
    checkLocalStorage: function() {
        const savedData = localStorage.getItem('workout_draft');
        if (savedData) {
            try {
                const data = JSON.parse(savedData);
                const nameInput = document.querySelector('input[name="name"]');

                // Check if data is not older than 1 hour
                const savedTime = new Date(data.timestamp);
                const now = new Date();
                const hoursDiff = Math.abs(now - savedTime) / 36e5;

                if (hoursDiff < 1 && nameInput && data.name) {
                    if (confirm('Wil je verder gaan met je workout "' + data.name + '"?')) {
                        nameInput.value = data.name;
                        this.workoutName = data.name;
                        this.updateProgress();
                    } else {
                        localStorage.removeItem('workout_draft');
                    }
                }
            } catch (e) {
                console.error('Error parsing saved data:', e);
                localStorage.removeItem('workout_draft');
            }
        }
    },

    // Save to localStorage
    saveToLocalStorage: function() {
        const data = {
            name: this.workoutName,
            timestamp: new Date().toISOString()
        };
        try {
            localStorage.setItem('workout_draft', JSON.stringify(data));
        } catch (e) {
            console.error('Error saving to localStorage:', e);
        }
    },

    // Update progress indicators
    updateProgress: function() {
        const steps = document.querySelectorAll('.step');

        // Step 1: Name
        if (this.workoutName.trim().length > 0) {
            if (steps[1]) {
                steps[1].classList.add('active');
            }
            this.showExerciseSection();
        } else {
            if (steps[1]) {
                steps[1].classList.remove('active');
            }
            this.hideExerciseSection();
        }

        // Step 3: Configuration
        const exerciseCount = document.querySelectorAll('.exercise-block, .active-workout-block').length;
        if (exerciseCount > 0 && steps[2]) {
            steps[2].classList.add('active');
        }
    },

    // Show exercise section with animation
    showExerciseSection: function() {
        const addBtn = document.getElementById('add-exercise-btn');
        const instruction = document.getElementById('exercise-instruction');
        const emptyState = document.getElementById('empty-state');
        const submitBtn = document.getElementById('submit-btn');

        if (addBtn) {
            addBtn.style.display = 'inline-flex';
            setTimeout(function() {
                addBtn.style.opacity = '1';
                addBtn.style.transform = 'scale(1)';
            }, 100);
        }

        if (instruction) {
            instruction.style.display = 'block';
            instruction.classList.add('fade-in');
        }

        if (emptyState) {
            const h3 = emptyState.querySelector('h3');
            const p = emptyState.querySelector('p');
            if (h3) {
                h3.textContent = '🎯 Klaar om oefeningen toe te voegen!';
            }
            if (p) {
                p.textContent = 'Klik op "Voeg oefening toe" om te beginnen';
            }

            // Add pulse animation to draw attention
            emptyState.classList.add('pulse');
            setTimeout(function() {
                emptyState.classList.remove('pulse');
            }, 1000);
        }

        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.classList.add('ready');
        }

        this.showMotivation();
    },

    // Hide exercise section
    hideExerciseSection: function() {
        const addBtn = document.getElementById('add-exercise-btn');
        const instruction = document.getElementById('exercise-instruction');
        const submitBtn = document.getElementById('submit-btn');

        if (addBtn) {
            addBtn.style.display = 'none';
        }
        if (instruction) {
            instruction.style.display = 'none';
        }
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.classList.remove('ready');
        }
    },

    // Show motivation message
    showMotivation: function() {
        const messages = [
            '🔥 Geweldig! Je bent goed bezig!',
            '💪 Super! Laten we een killer workout maken!',
            '🎯 Perfect! Dit wordt een top workout!',
            '⚡ Yes! Je motivatie is aanstekelijk!',
            '🏆 Fantastisch! Success starts here!'
        ];

        const randomMessage = messages[Math.floor(Math.random() * messages.length)];
        const motivationDiv = document.getElementById('motivation');

        if (motivationDiv) {
            const textElement = motivationDiv.querySelector('.motivation-text');
            if (textElement) {
                textElement.textContent = randomMessage;
            }
            motivationDiv.style.display = 'block';
            motivationDiv.classList.add('bounce-in');
        }
    },

    // Update exercise count
    updateExerciseCount: function() {
        const exercises = document.querySelectorAll('.exercise-block, .active-workout-block');
        const count = exercises.length;

        // Update any count displays
        const countElements = document.querySelectorAll('.exercise-count');
        countElements.forEach(function(el) {
            el.textContent = count;
        });

        // Show/hide empty state
        const emptyState = document.getElementById('empty-state');
        const exercisesList = document.getElementById('exercises-list');

        if (count === 0 && emptyState) {
            emptyState.style.display = 'block';
            if (exercisesList) {
                exercisesList.style.display = 'none';
            }
        } else if (count > 0) {
            if (emptyState) {
                emptyState.style.display = 'none';
            }
            if (exercisesList) {
                exercisesList.style.display = 'block';
            }
        }

        return count;
    },

    // Validate form before submission
    validateForm: function() {
        const nameInput = document.querySelector('input[name="name"]');

        if (!nameInput || nameInput.value.trim().length === 0) {
            this.showError('Geef je workout eerst een naam!');
            if (nameInput) {
                nameInput.focus();
            }
            return false;
        }

        // Optional: warn if no exercises
        const exerciseCount = this.updateExerciseCount();
        if (exerciseCount === 0) {
            return confirm('Je hebt nog geen oefeningen toegevoegd. Wil je de workout toch opslaan?');
        }

        return true;
    },

    // Show error message
    showError: function(message) {
        // Create or update error toast
        let errorToast = document.getElementById('error-toast');
        if (!errorToast) {
            errorToast = document.createElement('div');
            errorToast.id = 'error-toast';
            errorToast.className = 'error-toast';
            errorToast.innerHTML = '';
            document.body.appendChild(errorToast);
        }

        errorToast.innerHTML = '<span class="toast-icon">⚠️</span><span class="toast-message">' + message + '</span>';
        errorToast.style.display = 'flex';

        setTimeout(function() {
            errorToast.style.opacity = '0';
            setTimeout(function() {
                errorToast.style.display = 'none';
                errorToast.style.opacity = '1';
            }, 300);
        }, 3000);
    },

    // Animate intro elements
    animateIntro: function() {
        // Fade in elements sequentially
        const elements = [
            '.workout-creation-progress',
            '.step-instruction',
            '.workout-name',
            '.name-suggestions'
        ];

        elements.forEach(function(selector, index) {
            const element = document.querySelector(selector);
            if (element) {
                setTimeout(function() {
                    element.style.opacity = '0';
                    element.style.transform = 'translateY(20px)';
                    element.style.transition = 'all 0.5s ease';

                    setTimeout(function() {
                        element.style.opacity = '1';
                        element.style.transform = 'translateY(0)';
                    }, 50);
                }, index * 100);
            }
        });

        // Focus on name input after animation
        setTimeout(function() {
            const nameInput = document.querySelector('input[name="name"]');
            if (nameInput) {
                nameInput.focus();
            }
        }, 500);
    }
};

// Helper function for workout name suggestions (global scope for onclick)
function setWorkoutName(name) {
    const input = document.querySelector('input[name="name"]');
    if (input) {
        input.value = name;
        input.focus();

        // Trigger input event for update
        const event = new Event('input', { bubbles: true });
        input.dispatchEvent(event);

        // Animation feedback
        input.style.backgroundColor = '#fffbf0';
        setTimeout(function() {
            input.style.backgroundColor = '';
        }, 500);
    }
}

// Helper function to check workout name (global scope)
function checkWorkoutName() {
    const nameInput = document.querySelector('input[name="name"]');
    const submitBtn = document.getElementById('submit-btn');
    const addExerciseBtn = document.getElementById('add-exercise-btn');
    const emptyState = document.getElementById('empty-state');
    const exerciseInstruction = document.getElementById('exercise-instruction');
    const motivationMsg = document.getElementById('motivation');

    if (nameInput && nameInput.value.trim().length > 0) {
        // Activeer stap 2
        const step2 = document.querySelector('.step[data-step="2"]');
        if (step2) {
            step2.classList.add('active');
        }

        // Toon oefening instructies en knop
        if (addExerciseBtn) {
            addExerciseBtn.style.display = 'inline-flex';
        }
        if (exerciseInstruction) {
            exerciseInstruction.style.display = 'block';
        }
        if (submitBtn) {
            submitBtn.disabled = false;
        }

        // Update empty state
        if (emptyState) {
            const h3 = emptyState.querySelector('h3');
            const p = emptyState.querySelector('p');
            if (h3) {
                h3.textContent = 'Klaar om oefeningen toe te voegen!';
            }
            if (p) {
                p.textContent = 'Klik op "Voeg oefening toe" om te beginnen';
            }
        }

        // Toon motivatie
        if (motivationMsg) {
            motivationMsg.style.display = 'block';
        }
    } else {
        // Reset naar stap 1
        const step2 = document.querySelector('.step[data-step="2"]');
        if (step2) {
            step2.classList.remove('active');
        }

        if (addExerciseBtn) {
            addExerciseBtn.style.display = 'none';
        }
        if (exerciseInstruction) {
            exerciseInstruction.style.display = 'none';
        }
        if (submitBtn) {
            submitBtn.disabled = true;
        }
        if (motivationMsg) {
            motivationMsg.style.display = 'none';
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize main workflow
    WorkoutCreation.init();

    // Additional event listeners for existing functions
    const nameInput = document.querySelector('input[name="name"]');
    if (nameInput) {
        nameInput.addEventListener('input', checkWorkoutName);
        // Check on load
        checkWorkoutName();
    }
});

// Helper function to update exercise order (for drag & drop)
function updateExerciseOrder() {
    const blocks = document.querySelectorAll('.active-workout-block');
    const order = Array.from(blocks).map(function(block) {
        return block.dataset.exerciseId;
    }).filter(function(id) {
        return id;
    });

    // Activeer stap 3 als er oefeningen zijn
    if (order.length > 0) {
        const step3 = document.querySelector('.step[data-step="3"]');
        if (step3) {
            step3.classList.add('active');
        }
    }

    return order;
}
document.addEventListener('DOMContentLoaded', function () {
    // Add set functionality
    document.querySelectorAll('.active-workout-btn').forEach(button => {
        const action = button.dataset.action;

        if (action === 'add') {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                const workoutBlock = this.closest('.active-workout-block');
                if (!workoutBlock) {
                    console.error('Workout block not found');
                    return;
                }
                const wpeId = workoutBlock.dataset.wpeId;
                const sessionId = workoutBlock.dataset.sessionId;
                const setSection = workoutBlock.querySelector('.set-section');
                if (!setSection) {
                    console.error('Set section not found');
                    return;
                }
                const sets = setSection.querySelectorAll('.active-workout-set');
                const setNum = sets.length;
                const isCardio = workoutBlock.dataset.isCardio === 'true';

                const newSet = document.createElement('div');
                newSet.className = 'active-workout-set';
                if (isCardio) {
                    newSet.innerHTML = `
                        <input type="number" name="duration_${wpeId}_${setNum}" min="0.1" step="0.1" placeholder="Duur (min)" class="set-input duration-input" oninput="this.value = this.value.replace(/[^0-9.]/g, '')">
                        <input type="number" name="distance_${wpeId}_${setNum}" min="0" step="0.1" placeholder="Afstand (km)" class="set-input distance-input" oninput="this.value = this.value.replace(/[^0-9.]/g, '')">
                        <label class="custom-checkbox">
                            <input type="checkbox" name="completed_${wpeId}_${setNum}">
                            <span class="checkmark"></span>
                        </label>
                    `;
                } else {
                    newSet.innerHTML = `
                        <input type="number" name="reps_${wpeId}_${setNum}" min="1" step="1" placeholder="reps" class="set-input reps-input" oninput="this.value = this.value.replace(/[^0-9]/g, '')">
                        <input type="number" name="weight_${wpeId}_${setNum}" min="0" step="0.1" placeholder="KG" class="set-input weight-input" oninput="this.value = this.value.replace(/[^0-9.]/g, '')">
                        <label class="custom-checkbox">
                            <input type="checkbox" name="completed_${wpeId}_${setNum}">
                            <span class="checkmark"></span>
                        </label>
                    `;
                }
                setSection.appendChild(newSet);

                // Auto-save when inputs change
                const inputs = newSet.querySelectorAll('.set-input');
                inputs.forEach(input => {
                    input.addEventListener('change', function () {
                        saveSetToDatabase(wpeId, setNum, newSet, sessionId, isCardio);
                    });
                });

                // Auto-save when checkbox is checked
                const checkbox = newSet.querySelector('input[type="checkbox"]');
                checkbox.addEventListener('change', function () {
                    if (this.checked) {
                        saveSetToDatabase(wpeId, setNum, newSet, sessionId, isCardio);
                    }
                });
            });
        }

        if (action === 'complete') {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                const workoutBlock = this.closest('.active-workout-block');
                if (!workoutBlock) {
                    console.error('Workout block not found');
                    return;
                }
                const wpeId = workoutBlock.dataset.wpeId;
                const sessionId = workoutBlock.dataset.sessionId;
                const isCardio = workoutBlock.dataset.isCardio === 'true';
                const checkboxes = workoutBlock.querySelectorAll('.custom-checkbox input[type="checkbox"]');

                checkboxes.forEach((checkbox, index) => {
                    checkbox.checked = true;
                    const setElement = checkbox.closest('.active-workout-set');
                    saveSetToDatabase(wpeId, index, setElement, sessionId, isCardio);
                });
                updateAddSetButtonVisibility(workoutBlock);
            });
        }
    });
});

async function saveSetToDatabase(wpeId, setNum, setElement, sessionId, isCardio) {
    if (!setElement) {
        console.error(`Set element not found for wpeId=${wpeId}, setNum=${setNum}`);
        return;
    }

    const completedInput = setElement.querySelector(`input[name="completed_${wpeId}_${setNum}"]`);
    if (!completedInput) {
        console.error(`Completed input not found for wpeId=${wpeId}, setNum=${setNum}`);
        return;
    }

    const completed = completedInput.checked;
    let data = { wpe_id: wpeId, set_number: setNum, completed: completed, session_id: sessionId };

    if (isCardio) {
        const durationInput = setElement.querySelector(`input[name="duration_${wpeId}_${setNum}"]`);
        const distanceInput = setElement.querySelector(`input[name="distance_${wpeId}_${setNum}"]`);
        if (!durationInput || !distanceInput) {
            console.error(`Cardio inputs not found for wpeId=${wpeId}, setNum=${setNum}`);
            return;
        }
        data.duration_minutes = parseFloat(durationInput.value) || 0;
        data.distance_km = parseFloat(distanceInput.value) || 0;
    } else {
        const repsInput = setElement.querySelector(`input[name="reps_${wpeId}_${setNum}"]`);
        const weightInput = setElement.querySelector(`input[name="weight_${wpeId}_${setNum}"]`);
        if (!repsInput || !weightInput) {
            console.error(`Strength inputs not found for wpeId=${wpeId}, setNum=${setNum}`);
            return;
        }
        data.reps = parseFloat(repsInput.value) || 0;
        data.weight = parseFloat(weightInput.value) || 0;
    }

    if (completed && (isCardio ? data.duration_minutes > 0 : data.reps > 0)) {
        try {
            const response = await fetch('/sessions/save_set', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (result.success) {
                setElement.classList.add('set-saved');
                console.log('Set saved successfully:', result);
            } else {
                console.error('Failed to save set:', result.message);
            }
        } catch (error) {
            console.error('Error saving set:', error);
        }
    }
    updateAddSetButtonVisibility(setElement.closest('.active-workout-block'));
}

function updateAddSetButtonVisibility(workoutBlock) {
    if (!workoutBlock) return;
    const checkboxes = workoutBlock.querySelectorAll('.custom-checkbox input[type="checkbox"]');
    const allCompleted = [...checkboxes].every(cb => cb.checked);
    const addSetBtn = workoutBlock.querySelector('.active-workout-btn[data-action="add"]');
    if (addSetBtn) {
        addSetBtn.style.display = allCompleted ? 'none' : 'inline-block';
    }
}
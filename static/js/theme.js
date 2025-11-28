// static/js/theme.js

document.addEventListener('DOMContentLoaded', function() {
    const themeToggleButton = document.getElementById('theme-toggle-btn');
    const sunIcon = document.getElementById('theme-icon-sun');
    const moonIcon = document.getElementById('theme-icon-moon');
    const body = document.body;

    function applyTheme(theme) {
        body.classList.remove('theme-white');

        if (theme === 'white') {
            body.classList.add('theme-white');
            if (sunIcon) sunIcon.style.display = 'block';
            if (moonIcon) moonIcon.style.display = 'none';
        } else {
            if (sunIcon) sunIcon.style.display = 'none';
            if (moonIcon) moonIcon.style.display = 'block';
        }

        localStorage.setItem('selectedTheme', theme);

        // 🔥 NOVO: se existir a função renderChart, re-renderiza o gráfico
        if (typeof window.renderChart === "function") {
            window.renderChart(theme);
        }
    }


    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', function() {
            const isWhite = body.classList.contains('theme-white');
            const newTheme = isWhite ? 'black' : 'white';
            applyTheme(newTheme);
        });
    }

    // Carrega o tema salvo ao iniciar a página
    const savedTheme = localStorage.getItem('selectedTheme') || 'black';
    applyTheme(savedTheme);

    // 🔥 Re-renderiza os gráficos da página atual, se houver
    if (typeof window.renderCharts === "function") {
        window.renderCharts();
    }

});
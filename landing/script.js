(function () {
    const slides = document.querySelectorAll('.bg-slide');
    if (slides.length <= 1) return;

    let current = 0;
    const intervalMs = 10000;

    setInterval(function () {
        slides[current].classList.remove('active');
        current = (current + 1) % slides.length;
        slides[current].classList.add('active');
    }, intervalMs);
})();

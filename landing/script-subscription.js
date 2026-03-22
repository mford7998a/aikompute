/* ============================================
   AIKompute Landing Page — Subscription Version JS
   ============================================ */

document.addEventListener('DOMContentLoaded', () => {

    // ---- Navbar scroll effect ----
    const navbar = document.getElementById('navbar');
    let lastScroll = 0;

    window.addEventListener('scroll', () => {
        const scrollY = window.scrollY;
        if (scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
        lastScroll = scrollY;
    }, { passive: true });

    // ---- Mobile menu toggle ----
    const mobileToggle = document.getElementById('mobile-toggle');
    const navLinks = document.querySelector('.nav-links');
    const navActions = document.querySelector('.nav-actions');

    if (mobileToggle) {
        mobileToggle.addEventListener('click', () => {
            navLinks.classList.toggle('open');
            navActions.classList.toggle('open');
            mobileToggle.classList.toggle('active');
        });
    }

    // Close mobile menu on link click
    document.querySelectorAll('.nav-links .nav-link').forEach(link => {
        link.addEventListener('click', () => {
            navLinks.classList.remove('open');
            navActions.classList.remove('open');
            mobileToggle.classList.remove('active');
        });
    });

    // ---- Code tab switching ----
    const codeTabs = document.querySelectorAll('.code-tab');
    const codeBlocks = document.querySelectorAll('.code-block');

    codeTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const lang = tab.dataset.lang;

            codeTabs.forEach(t => t.classList.remove('active'));
            codeBlocks.forEach(b => b.classList.remove('active'));

            tab.classList.add('active');
            document.querySelector(`.code-block[data-lang="${lang}"]`).classList.add('active');
        });
    });

    // ---- Copy code button ----
    const copyBtn = document.getElementById('copy-code-btn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const activeBlock = document.querySelector('.code-block.active code');
            if (activeBlock) {
                navigator.clipboard.writeText(activeBlock.textContent).then(() => {
                    copyBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 7L6 10L11 4" stroke="#10b981" stroke-width="2" stroke-linecap="round"/></svg>';
                    setTimeout(() => {
                        copyBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="4" y="4" width="9" height="9" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M10 4V2.5A1.5 1.5 0 008.5 1H2.5A1.5 1.5 0 001 2.5V8.5A1.5 1.5 0 002.5 10H4" stroke="currentColor" stroke-width="1.5"/></svg>';
                    }, 2000);
                });
            }
        });
    }

    // ---- Billing Toggle (Monthly / Annual) ----
    const toggleBtns = document.querySelectorAll('.toggle-btn');
    const priceValues = document.querySelectorAll('.price-value');
    const periodTexts = document.querySelectorAll('.period-text');

    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const period = btn.dataset.period;

            toggleBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            priceValues.forEach(el => {
                const monthly = el.dataset.monthly;
                const annual = el.dataset.annual;
                
                if (period === 'annual') {
                    el.textContent = annual;
                } else {
                    el.textContent = monthly;
                }

                // Add animation
                el.style.transform = 'translateY(-5px)';
                el.style.opacity = '0';
                setTimeout(() => {
                    el.style.transition = 'all 0.3s ease';
                    el.style.transform = 'translateY(0)';
                    el.style.opacity = '1';
                }, 50);
            });

            periodTexts.forEach(el => {
                if (period === 'annual') {
                    el.textContent = 'per month, billed annually';
                } else {
                    el.textContent = 'per month';
                }
            });
        });
    });

    // ---- FAQ accordion ----
    document.querySelectorAll('.faq-question').forEach(question => {
        question.addEventListener('click', () => {
            const item = question.parentElement;
            const isOpen = item.classList.contains('open');

            // Close all
            document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));

            // Toggle current
            if (!isOpen) {
                item.classList.add('open');
                question.setAttribute('aria-expanded', 'true');
            } else {
                question.setAttribute('aria-expanded', 'false');
            }
        });
    });

    // ---- Counter animation ----
    function animateCounter(element, target, duration = 2000, decimal = false, suffix = '') {
        const start = 0;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease out cubic
            const ease = 1 - Math.pow(1 - progress, 3);
            const current = start + (target - start) * ease;

            if (decimal) {
                element.textContent = current.toFixed(1) + suffix;
            } else if (target >= 1000000) {
                element.textContent = (current / 1000000).toFixed(1) + 'M' + suffix;
            } else if (target >= 1000) {
                element.textContent = Math.floor(current).toLocaleString() + suffix;
            } else {
                element.textContent = Math.floor(current) + suffix;
            }

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }

        requestAnimationFrame(update);
    }

    // ---- Scroll reveal ----
    const revealElements = document.querySelectorAll(
        '.feature-card, .step-card, .pricing-card, .dx-card, .faq-item, .proof-item'
    );

    const counterElements = document.querySelectorAll('.proof-number');
    let countersAnimated = false;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');

                // Animate counters when proof section is visible
                if (entry.target.classList.contains('proof-item') && !countersAnimated) {
                    countersAnimated = true;
                    counterElements.forEach(el => {
                        const target = parseFloat(el.dataset.count);
                        const suffix = el.dataset.suffix || '';
                        const decimal = el.dataset.decimal === 'true';
                        animateCounter(el, target, 2200, decimal, suffix);
                    });
                }

                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.15,
        rootMargin: '0px 0px -50px 0px'
    });

    revealElements.forEach(el => {
        el.classList.add('reveal');
        observer.observe(el);
    });

    // ---- Smooth scroll for anchor links ----
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // ---- Staggered animation for grid items ----
    const staggerContainers = document.querySelectorAll('.features-grid, .pricing-grid, .dx-grid');

    staggerContainers.forEach(container => {
        const items = container.children;
        Array.from(items).forEach((item, index) => {
            item.style.transitionDelay = `${index * 0.1}s`;
        });
    });

});

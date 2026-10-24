 /* =========================================
           JavaScript: Partículas, Idioma y Menú
           ========================================= */
        
        // --- Selector de Idioma ---
        function setLang(lang) {
            // Actualizar botones
            document.getElementById('btn-es').classList.remove('active');
            document.getElementById('btn-en').classList.remove('active');
            document.getElementById('btn-' + lang).classList.add('active');

            // Mostrar/Ocultar contenido
            const elementsEs = document.querySelectorAll('.lang-es');
            const elementsEn = document.querySelectorAll('.lang-en');

            if (lang === 'es') {
                elementsEs.forEach(el => el.style.display = 'block');
                elementsEn.forEach(el => el.style.display = 'none');
            } else {
                elementsEs.forEach(el => el.style.display = 'none');
                elementsEn.forEach(el => el.style.display = 'block');
            }
        }

        // --- Toggle Menú Mobile ---
        function toggleSidebar() {
            const sidebar = document.getElementById('sidebar');
            sidebar.classList.toggle('active');
        }

        // Cierra sidebar al hacer click en un link en móvil
        document.querySelectorAll('.sidebar a').forEach(link => {
            link.addEventListener('click', () => {
                if(window.innerWidth <= 768) {
                    document.getElementById('sidebar').classList.remove('active');
                }
            });
        });

        // --- Partículas (Efecto Landing Page adaptado) ---
        const canvas = document.getElementById('particle-canvas');
        const ctx = canvas.getContext('2d');
        let particlesArray = [];
        const numberOfParticles = window.innerWidth < 768 ? 40 : 80; 

        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        window.addEventListener('resize', function() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            initParticles();
        });

        class Particle {
            constructor(x, y, directionX, directionY, size, color) {
                this.x = x;
                this.y = y;
                this.directionX = directionX;
                this.directionY = directionY;
                this.size = size;
                this.color = color;
            }
            draw() {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2, false);
                ctx.fillStyle = this.color;
                ctx.fill();
            }
            update() {
                if (this.x > canvas.width || this.x < 0) this.directionX = -this.directionX;
                if (this.y > canvas.height || this.y < 0) this.directionY = -this.directionY;
                
                this.x += this.directionX * 0.5; // Movimiento más lento para la lectura
                this.y += this.directionY * 0.5;
                this.draw();
            }
        }

        function initParticles() {
            particlesArray = [];
            for (let i = 0; i < numberOfParticles; i++) {
                let size = (Math.random() * 2) + 1;
                let x = (Math.random() * ((innerWidth - size * 2) - (size * 2)) + size * 2);
                let y = (Math.random() * ((innerHeight - size * 2) - (size * 2)) + size * 2);
                let directionX = (Math.random() * 1) - 0.5;
                let directionY = (Math.random() * 1) - 0.5;
                let color = '#8c9eff'; 
                particlesArray.push(new Particle(x, y, directionX, directionY, size, color));
            }
        }

        function connectParticles() {
            let opacityValue = 1;
            for (let a = 0; a < particlesArray.length; a++) {
                for (let b = a; b < particlesArray.length; b++) {
                    let distance = ((particlesArray[a].x - particlesArray[b].x) * (particlesArray[a].x - particlesArray[b].x))
                                 + ((particlesArray[a].y - particlesArray[b].y) * (particlesArray[a].y - particlesArray[b].y));
                    
                    if (distance < (canvas.width/8) * (canvas.height/8)) {
                        opacityValue = 1 - (distance / 15000);
                        ctx.strokeStyle = 'rgba(140, 158, 255,' + (opacityValue * 0.3) + ')';
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        ctx.moveTo(particlesArray[a].x, particlesArray[a].y);
                        ctx.lineTo(particlesArray[b].x, particlesArray[b].y);
                        ctx.stroke();
                    }
                }
            }
        }

        function animateParticles() {
            requestAnimationFrame(animateParticles);
            ctx.clearRect(0, 0, innerWidth, innerHeight);
            for (let i = 0; i < particlesArray.length; i++) {
                particlesArray[i].update();
            }
            connectParticles();
        }

        initParticles();
        animateParticles();
html: str = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backend CTC - API Documentation</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow-x: hidden;
        }

        .container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 50px;
            border-radius: 25px;
            text-align: center;
            max-width: 700px;
            width: 90%;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.2);
            animation: slideUp 0.8s ease-out;
        }

        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(50px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .logo {
            font-size: 4em;
            margin-bottom: 20px;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }

        h1 {
            color: white;
            font-size: 3em;
            margin-bottom: 15px;
            font-weight: 700;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }

        .subtitle {
            color: rgba(255, 255, 255, 0.9);
            font-size: 1.3em;
            margin-bottom: 40px;
            line-height: 1.6;
        }

        .api-links {
            display: flex;
            gap: 25px;
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 40px;
        }

        .api-btn {
            display: inline-flex;
            align-items: center;
            gap: 12px;
            padding: 18px 35px;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            text-decoration: none;
            border-radius: 50px;
            font-weight: 600;
            font-size: 1.1em;
            transition: all 0.3s ease;
            border: 2px solid rgba(255, 255, 255, 0.3);
            backdrop-filter: blur(10px);
        }

        .api-btn:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            border-color: rgba(255, 255, 255, 0.5);
        }

        .api-btn i {
            font-size: 1.2em;
        }

        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .feature {
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: transform 0.3s ease;
        }

        .feature:hover {
            transform: translateY(-5px);
        }

        .feature i {
            font-size: 2em;
            color: #FFD700;
            margin-bottom: 10px;
        }

        .feature h3 {
            color: white;
            margin-bottom: 8px;
            font-size: 1.1em;
        }

        .feature p {
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.9em;
        }

        .footer {
            border-top: 1px solid rgba(255, 255, 255, 0.2);
            padding-top: 25px;
            color: rgba(255, 255, 255, 0.7);
        }

        .version-badge {
            display: inline-block;
            background: rgba(255, 255, 255, 0.2);
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            margin-top: 10px;
        }

        @media (max-width: 768px) {
            .container {
                padding: 30px 25px;
                margin: 20px;
            }

            h1 {
                font-size: 2.2em;
            }

            .api-links {
                flex-direction: column;
                align-items: center;
            }

            .api-btn {
                width: 250px;
                justify-content: center;
            }

            .features {
                grid-template-columns: 1fr;
            }
        }

        .particles {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: -1;
        }

        .particle {
            position: absolute;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            animation: float 6s ease-in-out infinite;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-20px) rotate(180deg); }
        }
    </style>
</head>
<body>
    <div class="particles" id="particles"></div>
    
    <div class="container">
        <div class="logo">🚀</div>
        <h1>API - CTC</h1>
        <p class="subtitle">
            Bienvenido a nuestra API REST. Explora la documentación interactiva 
            y descubre todas las funcionalidades disponibles.
        </p>

        <div class="api-links">
            <a href="/docs" class="api-btn">
                <i class="fas fa-book"></i>
                Swagger UI
            </a>
            <a href="/redoc" class="api-btn">
                <i class="fas fa-file-alt"></i>
                ReDoc
            </a>
        </div>

        <div class="features">
            <div class="feature">
                <i class="fas fa-bolt"></i>
                <h3>Alta Performance</h3>
                <p>Construido con FastAPI para máxima velocidad</p>
            </div>
            <div class="feature">
                <i class="fas fa-shield-alt"></i>
                <h3>Seguro</h3>
                <p>Autenticación y validación integrada</p>
            </div>
            <div class="feature">
                <i class="fas fa-code"></i>
                <h3>Moderno</h3>
                <p>Desarrollo con las últimas tecnologías</p>
            </div>
            <div class="feature">
                <i class="fas fa-user"></i>
                <h3>Equipo de Desarrollo</h3>
                <p>Ezequiel Viera y Eugenia Finozzi</p>
            </div>
        </div>



        <div class="footer">
            <p><i class="fas fa-code"></i> Desarrollado con FastAPI</p>
            <span class="version-badge">
                <i class="fas fa-tag"></i> v1.0.0
            </span>
        </div>
    </div>

    <script>
        // Crear partículas animadas
        function createParticles() {
            const particlesContainer = document.getElementById('particles');
            const particleCount = 50;

            for (let i = 0; i < particleCount; i++) {
                const particle = document.createElement('div');
                particle.className = 'particle';
                
                const size = Math.random() * 6 + 2;
                particle.style.width = size + 'px';
                particle.style.height = size + 'px';
                particle.style.left = Math.random() * 100 + '%';
                particle.style.top = Math.random() * 100 + '%';
                particle.style.animationDelay = Math.random() * 6 + 's';
                particle.style.animationDuration = (Math.random() * 4 + 4) + 's';
                
                particlesContainer.appendChild(particle);
            }
        }

        // Inicializar partículas cuando carga la página
        document.addEventListener('DOMContentLoaded', createParticles);

        // Efecto de hover en los botones
        document.querySelectorAll('.api-btn').forEach(btn => {
            btn.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-3px) scale(1.05)';
            });
            
            btn.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0) scale(1)';
            });
        });
    </script>
</body>
</html>
"""
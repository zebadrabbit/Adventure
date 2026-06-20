/**
 * Combat Visual Effects System
 * Provides floating damage numbers, hit animations, spell effects, and status indicators
 */

function uiColor(name, fallback) {
    const v = getComputedStyle(document.documentElement)
        .getPropertyValue(`--ui-${name}`)
        .trim();
    return v || fallback;
}

class CombatEffects {
    constructor() {
        this.effectsContainer = null;
        this.particleCanvas = null;
        this.particleCtx = null;
        this.particles = [];
        this.animating = false;
        this.init();
    }

    init() {
        // Create effects container for floating text
        this.effectsContainer = document.createElement('div');
        this.effectsContainer.id = 'combat-effects-container';
        this.effectsContainer.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 9999;
        `;
        document.body.appendChild(this.effectsContainer);

        // Create particle canvas for spell effects
        this.particleCanvas = document.createElement('canvas');
        this.particleCanvas.id = 'combat-particles-canvas';
        this.particleCanvas.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            pointer-events: none;
            z-index: 9998;
        `;
        this.particleCtx = this.particleCanvas.getContext('2d');
        document.body.appendChild(this.particleCanvas);

        // Resize canvas to viewport
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());

        // Start animation loop
        this.startAnimationLoop();
    }

    resizeCanvas() {
        this.particleCanvas.width = window.innerWidth;
        this.particleCanvas.height = window.innerHeight;
    }

    startAnimationLoop() {
        const animate = () => {
            this.updateParticles();
            this.renderParticles();
            requestAnimationFrame(animate);
        };
        animate();
    }

    /**
     * Floating Damage Numbers
     */
    showDamage(targetElement, damage, options = {}) {
        const {
            isCritical = false,
            isHeal = false,
            isMiss = false,
            color = null,
            prefix = '',
            suffix = ''
        } = options;

        const rect = targetElement.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;

        const floater = document.createElement('div');
        floater.className = 'combat-damage-floater';

        let displayText = prefix;
        if (isMiss) {
            displayText += 'MISS!';
        } else {
            displayText += Math.abs(damage);
        }
        displayText += suffix;

        floater.textContent = displayText;

        // Styling
        let baseColor = color;
        if (!baseColor) {
            if (isHeal) baseColor = uiColor('success', '#4caf82');
            else if (isCritical) baseColor = uiColor('warning', '#d6a23a');
            else if (isMiss) baseColor = uiColor('text-dim', '#8d97a3');
            else baseColor = uiColor('danger', '#c0392b');
        }

        const fontSize = isCritical ? '2.5rem' : (isMiss ? '1.5rem' : '2rem');
        const fontWeight = isCritical ? '900' : '700';
        const textShadow = isCritical
            ? '0 0 10px rgba(251, 191, 36, 0.8), 0 0 20px rgba(251, 191, 36, 0.6), 2px 2px 4px rgba(0,0,0,0.8)'
            : '2px 2px 4px rgba(0,0,0,0.8), 0 0 8px rgba(0,0,0,0.5)';

        floater.style.cssText = `
            position: absolute;
            left: ${centerX}px;
            top: ${centerY}px;
            transform: translate(-50%, -50%);
            color: ${baseColor};
            font-size: ${fontSize};
            font-weight: ${fontWeight};
            font-family: 'Courier New', monospace;
            text-shadow: ${textShadow};
            pointer-events: none;
            z-index: 10000;
            animation: ${isCritical ? 'damageFloatCritical' : 'damageFloat'} 1.5s ease-out forwards;
        `;

        this.effectsContainer.appendChild(floater);

        // Random horizontal drift
        const drift = (Math.random() - 0.5) * 60;
        floater.style.setProperty('--drift-x', `${drift}px`);

        setTimeout(() => floater.remove(), 1500);

        // Add shake effect to target
        if (!isMiss && !isHeal) {
            this.shakeElement(targetElement, isCritical ? 'strong' : 'normal');
        }

        // Add flash effect
        if (!isMiss) {
            this.flashElement(targetElement, isHeal ? uiColor('success', '#4caf82') : uiColor('danger', '#c0392b'));
        }
    }

    /**
     * Shake Animation
     */
    shakeElement(element, intensity = 'normal') {
        const distance = intensity === 'strong' ? 8 : 4;
        const duration = intensity === 'strong' ? 500 : 300;

        element.style.animation = `shake-${intensity} ${duration}ms ease-in-out`;

        setTimeout(() => {
            element.style.animation = '';
        }, duration);
    }

    /**
     * Flash Animation
     */
    flashElement(element, color = uiColor('danger', '#c0392b')) {
        const originalBg = element.style.backgroundColor || '';
        const originalTransition = element.style.transition || '';

        element.style.transition = 'background-color 0.1s';
        element.style.backgroundColor = `${color}33`; // 20% opacity

        setTimeout(() => {
            element.style.backgroundColor = originalBg;
            setTimeout(() => {
                element.style.transition = originalTransition;
            }, 200);
        }, 100);
    }

    /**
     * Basic-attack slash: a brief X-shaped swipe across the target.
     */
    showAttackSlash(targetElement) {
        const el = document.createElement('div');
        el.className = 'combat-attack-slash';
        el.innerHTML = '<span class="combat-attack-slash-line combat-attack-slash-line-1"></span>' +
            '<span class="combat-attack-slash-line combat-attack-slash-line-2"></span>';
        targetElement.appendChild(el);
        setTimeout(() => el.remove(), 400);
    }

    /**
     * Defend flash: a brief shield icon over the defending character.
     */
    showDefendShield(targetElement) {
        const el = document.createElement('div');
        el.className = 'combat-defend-shield';
        el.innerHTML = '<i class="bi bi-shield-fill"></i>';
        targetElement.appendChild(el);
        setTimeout(() => el.remove(), 600);
    }

    /**
     * Particle System for Spell Effects
     */
    createParticles(sourceElement, targetElement, spell) {
        const sourceRect = sourceElement.getBoundingClientRect();
        const targetRect = targetElement.getBoundingClientRect();

        const startX = sourceRect.left + sourceRect.width / 2;
        const startY = sourceRect.top + sourceRect.height / 2;
        const endX = targetRect.left + targetRect.width / 2;
        const endY = targetRect.top + targetRect.height / 2;

        switch (spell) {
            case 'firebolt':
                this.createFirebolt(startX, startY, endX, endY);
                break;
            case 'ice_shard':
                this.createIceShard(startX, startY, endX, endY);
                break;
            case 'lightning':
                this.createLightning(startX, startY, endX, endY);
                break;
            case 'heal':
                this.createHealEffect(targetElement);
                break;
            default:
                this.createGenericProjectile(startX, startY, endX, endY);
        }
    }

    createFirebolt(startX, startY, endX, endY) {
        const distance = Math.sqrt((endX - startX) ** 2 + (endY - startY) ** 2);
        const duration = 600; // ms
        const particleCount = 30;

        for (let i = 0; i < particleCount; i++) {
            const delay = (i / particleCount) * 200; // Stagger particles
            setTimeout(() => {
                this.particles.push({
                    x: startX,
                    y: startY,
                    vx: (endX - startX) / duration * 16.67, // 60fps
                    vy: (endY - startY) / duration * 16.67,
                    life: duration,
                    maxLife: duration,
                    size: 8 + Math.random() * 8,
                    color: this.randomFireColor(),
                    type: 'fire',
                    trail: []
                });
            }, delay);
        }

        // Impact effect at target
        setTimeout(() => {
            this.createExplosion(endX, endY, 'fire');
        }, duration + 200);
    }

    createIceShard(startX, startY, endX, endY) {
        const duration = 400;
        const shardCount = 5;

        for (let i = 0; i < shardCount; i++) {
            const angle = (Math.PI / 4) * (i - shardCount / 2) / shardCount;
            const dx = endX - startX;
            const dy = endY - startY;
            const rotatedDx = dx * Math.cos(angle) - dy * Math.sin(angle);
            const rotatedDy = dx * Math.sin(angle) + dy * Math.cos(angle);

            this.particles.push({
                x: startX,
                y: startY,
                vx: rotatedDx / duration * 16.67,
                vy: rotatedDy / duration * 16.67,
                life: duration,
                maxLife: duration,
                size: 12,
                color: `rgba(147, 197, 253, ${0.8 + Math.random() * 0.2})`,
                type: 'ice',
                rotation: Math.random() * Math.PI * 2,
                rotationSpeed: (Math.random() - 0.5) * 0.2
            });
        }

        setTimeout(() => {
            this.createExplosion(endX, endY, 'ice');
        }, duration);
    }

    createLightning(startX, startY, endX, endY) {
        // Lightning bolt effect - instant with branching
        const segments = 10;
        const points = [{ x: startX, y: startY }];

        for (let i = 1; i < segments; i++) {
            const t = i / segments;
            const x = startX + (endX - startX) * t + (Math.random() - 0.5) * 30;
            const y = startY + (endY - startY) * t + (Math.random() - 0.5) * 30;
            points.push({ x, y });
        }
        points.push({ x: endX, y: endY });

        this.particles.push({
            type: 'lightning',
            points: points,
            life: 200,
            maxLife: 200,
            thickness: 3 + Math.random() * 3,
            color: '#fbbf24'
        });

        // Add branching bolts
        for (let i = 0; i < 3; i++) {
            const branchStart = points[Math.floor(Math.random() * points.length)];
            const branchEnd = {
                x: branchStart.x + (Math.random() - 0.5) * 100,
                y: branchStart.y + (Math.random() - 0.5) * 100
            };

            this.particles.push({
                type: 'lightning',
                points: [branchStart, branchEnd],
                life: 150,
                maxLife: 150,
                thickness: 1 + Math.random() * 2,
                color: '#fbbf24'
            });
        }

        // Flash at target
        setTimeout(() => {
            this.createExplosion(endX, endY, 'lightning');
        }, 100);
    }

    createHealEffect(targetElement) {
        const rect = targetElement.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;

        // Rising sparkles
        for (let i = 0; i < 20; i++) {
            setTimeout(() => {
                const angle = Math.random() * Math.PI * 2;
                const speed = 2 + Math.random() * 3;
                this.particles.push({
                    x: centerX + (Math.random() - 0.5) * rect.width,
                    y: centerY + rect.height / 2,
                    vx: Math.cos(angle) * speed * 0.3,
                    vy: -Math.abs(Math.sin(angle) * speed),
                    life: 1000 + Math.random() * 500,
                    maxLife: 1000,
                    size: 4 + Math.random() * 4,
                    color: `rgba(74, 222, 128, ${0.6 + Math.random() * 0.4})`,
                    type: 'sparkle'
                });
            }, i * 30);
        }

        // Glow effect on target
        this.flashElement(targetElement, uiColor('success', '#4caf82'));
    }

    createGenericProjectile(startX, startY, endX, endY) {
        const duration = 500;
        this.particles.push({
            x: startX,
            y: startY,
            vx: (endX - startX) / duration * 16.67,
            vy: (endY - startY) / duration * 16.67,
            life: duration,
            maxLife: duration,
            size: 12,
            color: '#a78bfa',
            type: 'magic'
        });
    }

    createExplosion(x, y, type = 'fire') {
        const particleCount = type === 'lightning' ? 15 : 25;
        const colors = {
            fire: ['#ef4444', '#f97316', '#fbbf24'],
            ice: ['#60a5fa', '#93c5fd', '#dbeafe'],
            lightning: ['#fbbf24', '#fde047', '#fef9c3']
        };

        for (let i = 0; i < particleCount; i++) {
            const angle = (Math.PI * 2 * i) / particleCount;
            const speed = 3 + Math.random() * 5;
            const colorArray = colors[type] || colors.fire;

            this.particles.push({
                x: x,
                y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                life: 400 + Math.random() * 300,
                maxLife: 600,
                size: 6 + Math.random() * 6,
                color: colorArray[Math.floor(Math.random() * colorArray.length)],
                type: 'explosion',
                gravity: type === 'ice' ? 0.05 : 0.1
            });
        }
    }

    randomFireColor() {
        const colors = [
            'rgba(239, 68, 68, 0.9)',   // Red
            'rgba(249, 115, 22, 0.9)',  // Orange
            'rgba(251, 191, 36, 0.9)',  // Yellow
            'rgba(252, 211, 77, 0.7)'   // Light yellow
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }

    updateParticles() {
        for (let i = this.particles.length - 1; i >= 0; i--) {
            const p = this.particles[i];
            p.life -= 16.67; // ~60fps

            if (p.life <= 0) {
                this.particles.splice(i, 1);
                continue;
            }

            if (p.type !== 'lightning') {
                p.x += p.vx || 0;
                p.y += p.vy || 0;

                if (p.gravity) {
                    p.vy += p.gravity;
                }

                if (p.type === 'fire' && p.trail) {
                    p.trail.push({ x: p.x, y: p.y });
                    if (p.trail.length > 5) p.trail.shift();
                }

                if (p.rotationSpeed) {
                    p.rotation = (p.rotation || 0) + p.rotationSpeed;
                }
            }
        }
    }

    renderParticles() {
        this.particleCtx.clearRect(0, 0, this.particleCanvas.width, this.particleCanvas.height);

        for (const p of this.particles) {
            const alpha = p.life / p.maxLife;
            this.particleCtx.globalAlpha = alpha;

            if (p.type === 'lightning') {
                this.renderLightning(p);
            } else if (p.type === 'ice') {
                this.renderIceShard(p);
            } else if (p.type === 'fire' && p.trail) {
                this.renderFireTrail(p);
            } else {
                this.renderCircle(p);
            }
        }

        this.particleCtx.globalAlpha = 1;
    }

    renderCircle(p) {
        this.particleCtx.fillStyle = p.color;
        this.particleCtx.beginPath();
        this.particleCtx.arc(p.x, p.y, p.size / 2, 0, Math.PI * 2);
        this.particleCtx.fill();

        // Glow effect for sparkles
        if (p.type === 'sparkle') {
            this.particleCtx.shadowBlur = 10;
            this.particleCtx.shadowColor = p.color;
            this.particleCtx.fill();
            this.particleCtx.shadowBlur = 0;
        }
    }

    renderFireTrail(p) {
        // Render trail
        if (p.trail.length > 1) {
            this.particleCtx.strokeStyle = p.color;
            this.particleCtx.lineWidth = p.size / 2;
            this.particleCtx.lineCap = 'round';
            this.particleCtx.beginPath();
            this.particleCtx.moveTo(p.trail[0].x, p.trail[0].y);
            for (let i = 1; i < p.trail.length; i++) {
                this.particleCtx.lineTo(p.trail[i].x, p.trail[i].y);
            }
            this.particleCtx.stroke();
        }

        // Render head
        this.renderCircle(p);
    }

    renderIceShard(p) {
        this.particleCtx.save();
        this.particleCtx.translate(p.x, p.y);
        this.particleCtx.rotate(p.rotation || 0);

        this.particleCtx.fillStyle = p.color;
        this.particleCtx.beginPath();
        this.particleCtx.moveTo(0, -p.size);
        this.particleCtx.lineTo(p.size / 3, p.size / 2);
        this.particleCtx.lineTo(-p.size / 3, p.size / 2);
        this.particleCtx.closePath();
        this.particleCtx.fill();

        this.particleCtx.restore();
    }

    renderLightning(p) {
        if (!p.points || p.points.length < 2) return;

        this.particleCtx.strokeStyle = p.color;
        this.particleCtx.lineWidth = p.thickness;
        this.particleCtx.lineCap = 'round';
        this.particleCtx.shadowBlur = 10;
        this.particleCtx.shadowColor = p.color;

        this.particleCtx.beginPath();
        this.particleCtx.moveTo(p.points[0].x, p.points[0].y);
        for (let i = 1; i < p.points.length; i++) {
            this.particleCtx.lineTo(p.points[i].x, p.points[i].y);
        }
        this.particleCtx.stroke();

        this.particleCtx.shadowBlur = 0;
    }

    /**
     * Status Effect Indicators
     */
    addStatusIndicator(targetElement, status, duration = 0) {
        const indicators = targetElement.querySelector('.status-indicators') || this.createStatusContainer(targetElement);

        const indicator = document.createElement('div');
        indicator.className = `status-indicator status-${status}`;
        indicator.title = status.charAt(0).toUpperCase() + status.slice(1);

        const icon = this.getStatusIcon(status);
        indicator.innerHTML = icon;

        indicators.appendChild(indicator);

        if (duration > 0) {
            setTimeout(() => indicator.remove(), duration);
        }

        return indicator;
    }

    createStatusContainer(targetElement) {
        const container = document.createElement('div');
        container.className = 'status-indicators';
        targetElement.appendChild(container);
        return container;
    }

    getStatusIcon(status) {
        const icons = {
            poison: '<i class="bi bi-droplet-fill text-success"></i>',
            burn: '<i class="bi bi-fire text-danger"></i>',
            freeze: '<i class="bi bi-snow text-info"></i>',
            stun: '<i class="bi bi-stars text-warning"></i>',
            shield: '<i class="bi bi-shield-fill-check text-primary"></i>',
            regen: '<i class="bi bi-heart-pulse-fill text-success"></i>',
            curse: '<i class="bi bi-moon-fill text-purple"></i>',
            blessed: '<i class="bi bi-sun-fill text-warning"></i>'
        };
        return icons[status] || '<i class="bi bi-question-circle"></i>';
    }

    removeStatusIndicator(targetElement, status) {
        const indicators = targetElement.querySelector('.status-indicators');
        if (indicators) {
            const indicator = indicators.querySelector(`.status-${status}`);
            if (indicator) indicator.remove();
        }
    }

    /**
     * Cleanup
     */
    destroy() {
        if (this.effectsContainer) this.effectsContainer.remove();
        if (this.particleCanvas) this.particleCanvas.remove();
        this.particles = [];
    }
}

// Initialize global combat effects instance
window.combatEffects = new CombatEffects();

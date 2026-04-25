import { useEffect, useRef } from 'react';

interface Props {
  density?: number;
  hue?: 'accent' | 'rust' | 'sage' | 'deep';
  motion?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const HUES: Record<NonNullable<Props['hue']>, string> = {
  accent: '139,115,85',
  rust: '168,90,74',
  sage: '107,126,90',
  deep: '61,49,38',
};

export default function ParcelWave({
  density = 120,
  hue = 'accent',
  motion = true,
  className,
  style,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let W = 0;
    let H = 0;
    let DPR = Math.min(window.devicePixelRatio || 1, 2);
    let particles: Array<{
      baseX: number;
      baseY: number;
      r: number;
      c: number;
      phase: number;
      rowPhase: number;
    }> = [];
    let raf = 0;
    const t0 = performance.now();
    const rgb = HUES[hue] || HUES.accent;

    function build() {
      particles = [];
      const cols = density;
      const rows = Math.floor(cols * 0.42);
      const spacingX = W / cols;
      const spacingY = H / rows;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const x = c * spacingX + (r % 2 ? spacingX / 2 : 0);
          const y = r * spacingY + H * 0.08;
          particles.push({
            baseX: x,
            baseY: y,
            r,
            c,
            phase: (c / cols) * Math.PI * 2,
            rowPhase: r / rows,
          });
        }
      }
    }

    function resize() {
      if (!canvas || !ctx) return;
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      W = canvas.clientWidth;
      H = canvas.clientHeight;
      canvas.width = W * DPR;
      canvas.height = H * DPR;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      build();
    }

    function draw(t: number) {
      if (!ctx) return;
      ctx.clearRect(0, 0, W, H);
      const time = (t - t0) * 0.001;

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        const rowWeight = 1 - p.rowPhase;
        const amp = 18 + rowWeight * 30;
        const wave =
          Math.sin(p.phase + time * 1.1 + p.rowPhase * 2.4) * amp +
          Math.cos(p.phase * 0.6 + time * 0.5) * (amp * 0.5);
        const yOffset = motion ? wave : Math.sin(p.phase + p.rowPhase * 2.4) * amp * 0.5;

        const x = p.baseX;
        const y = p.baseY + yOffset * (0.35 + rowWeight * 0.8);

        const depth = 0.25 + rowWeight * 0.85;
        const size = 0.7 + rowWeight * 1.1;
        const alpha = 0.12 + rowWeight * 0.55;

        ctx.fillStyle = `rgba(${rgb}, ${alpha * depth})`;
        ctx.beginPath();
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    }

    window.addEventListener('resize', resize);
    resize();
    raf = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(raf);
    };
  }, [density, hue, motion]);

  return (
    <div
      className={className}
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        pointerEvents: 'none',
        WebkitMaskImage:
          'linear-gradient(to bottom, transparent 0%, #000 22%, #000 78%, transparent 100%)',
        maskImage:
          'linear-gradient(to bottom, transparent 0%, #000 22%, #000 78%, transparent 100%)',
        ...style,
      }}
    >
      <canvas
        ref={canvasRef}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block' }}
      />
    </div>
  );
}

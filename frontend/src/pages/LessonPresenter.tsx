import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { lessonsAPI } from '../services/api';
import SceneRenderer from '../components/lesson/SceneRenderer';
import { useSceneMotion } from '../components/lesson/useSceneMotion';
import { esNivelInicial, type Asset, type LessonSpec } from '../types/lesson';
import '../styles/lesson-player.css';

/** Mantiene la pantalla encendida durante la clase.
 *
 * Cuarenta y cinco minutos de exposición sin tocar el notebook y el equipo
 * apaga la pantalla en medio de la explicación. Falla en silencio donde la API
 * no existe o el navegador la rechaza: es una mejora, no un requisito.
 */
function useWakeLock(activo: boolean) {
  useEffect(() => {
    if (!activo || !('wakeLock' in navigator)) return;
    let lock: WakeLockSentinel | null = null;
    let cancelado = false;

    const pedir = async () => {
      try {
        lock = await (navigator as Navigator).wakeLock.request('screen');
      } catch {
        /* sin wake lock la clase igual funciona */
      }
    };
    pedir();

    // El lock se pierde al cambiar de pestaña; hay que recuperarlo al volver.
    const alVolver = () => {
      if (!cancelado && document.visibilityState === 'visible') pedir();
    };
    document.addEventListener('visibilitychange', alVolver);

    return () => {
      cancelado = true;
      document.removeEventListener('visibilitychange', alVolver);
      lock?.release().catch(() => {});
    };
  }, [activo]);
}

/** Precarga todas las imágenes antes de la primera escena.
 *
 * Cargarlas escena por escena deja la pantalla en blanco a mitad de clase
 * cuando el wifi del colegio falla. Resuelve igual si alguna falla: se muestra
 * el alt.
 */
function usePrecarga(assets: Asset[]) {
  const [listo, setListo] = useState(false);
  useEffect(() => {
    const urls = assets.filter((a) => a.status === 'ready' && a.uri).map((a) => a.uri);
    if (urls.length === 0) {
      setListo(true);
      return;
    }
    let pendientes = urls.length;
    const terminar = () => {
      pendientes -= 1;
      if (pendientes <= 0) setListo(true);
    };
    urls.forEach((url) => {
      const img = new Image();
      img.onload = terminar;
      img.onerror = terminar;
      img.src = url;
    });
  }, [assets]);
  return listo;
}

export default function LessonPresenter() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [spec, setSpec] = useState<LessonSpec | null>(null);
  const [error, setError] = useState('');
  const [indice, setIndice] = useState(0);
  const [revelados, setRevelados] = useState(0);
  const [respuestaVisible, setRespuestaVisible] = useState(false);
  const [seleccionada, setSeleccionada] = useState('');
  const [controlesVisibles, setControlesVisibles] = useState(true);
  const [narracionAbierta, setNarracionAbierta] = useState(false);
  const contenedor = useRef<HTMLDivElement>(null);
  const escenaRef = useRef<HTMLDivElement>(null);
  const ocultarRef = useRef<number>();

  useEffect(() => {
    let vivo = true;
    lessonsAPI
      .present(Number(id))
      .then((r) => vivo && setSpec(r.data.spec))
      .catch(() => vivo && setError('No se pudo abrir la clase.'));
    return () => {
      vivo = false;
    };
  }, [id]);

  const escena = spec?.scenes[indice];
  const total = spec?.scenes.length ?? 0;
  const assets = useMemo(() => {
    const mapa: Record<string, Asset> = {};
    (spec?.assets ?? []).forEach((a) => { mapa[a.id] = a; });
    return mapa;
  }, [spec]);

  useWakeLock(Boolean(spec));
  const imagenesListas = usePrecarga(spec?.assets ?? []);

  const pasosTotales = escena?.type === 'process' ? escena.data.steps.length : 0;

  // Va antes de los returns condicionales: el orden de los hooks no puede
  // depender de si la clase ya cargó.
  useSceneMotion(
    escenaRef,
    escena?.id ?? '',
    escena?.type ?? 'concept',
    spec?.motion_defaults.enabled === false ? 'none' : (escena?.motion.preset ?? 'none'),
    escena?.motion.duration_ms ?? 500,
    escena?.motion.stagger_ms ?? 0,
  );

  const avanzar = useCallback(() => {
    // Dentro de una escena de proceso, avanzar revela el paso siguiente antes
    // de cambiar de escena: la progresión es el contenido.
    if (pasosTotales > 0 && revelados < pasosTotales) {
      setRevelados((r) => r + 1);
      return;
    }
    if (escena?.type === 'quiz' && !respuestaVisible) {
      setRespuestaVisible(true);
      return;
    }
    setIndice((i) => Math.min(i + 1, total - 1));
  }, [escena, pasosTotales, revelados, respuestaVisible, total]);

  const retroceder = useCallback(() => {
    if (pasosTotales > 0 && revelados > 0) {
      setRevelados((r) => r - 1);
      return;
    }
    setIndice((i) => Math.max(i - 1, 0));
  }, [pasosTotales, revelados]);

  // Al cambiar de escena se reinicia su estado interno.
  useEffect(() => {
    setRevelados(0);
    setRespuestaVisible(false);
    setSeleccionada('');
  }, [indice]);

  const salir = useCallback(() => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    navigate(`/clases/${id}/editar`);
  }, [id, navigate]);

  useEffect(() => {
    const teclado = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowRight': case ' ': case 'PageDown':
          e.preventDefault(); avanzar(); break;
        case 'ArrowLeft': case 'PageUp':
          e.preventDefault(); retroceder(); break;
        case 'n': case 'N':
          setNarracionAbierta((v) => !v); break;
        case 'Escape':
          if (!document.fullscreenElement) salir(); break;
      }
    };
    window.addEventListener('keydown', teclado);
    return () => window.removeEventListener('keydown', teclado);
  }, [avanzar, retroceder, salir]);

  // Los controles se esconden solos: en pantalla duplicada todo lo visible se
  // proyecta, y una barra fija sobre la clase es ruido para el curso.
  useEffect(() => {
    const mover = () => {
      setControlesVisibles(true);
      window.clearTimeout(ocultarRef.current);
      ocultarRef.current = window.setTimeout(() => setControlesVisibles(false), 3000);
    };
    mover();
    window.addEventListener('mousemove', mover);
    return () => {
      window.removeEventListener('mousemove', mover);
      window.clearTimeout(ocultarRef.current);
    };
  }, []);

  const pantallaCompleta = () => {
    const el = contenedor.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else el.requestFullscreen?.().catch(() => {});
  };

  if (error) {
    return (
      <div className="lesson-player" style={{ display: 'grid', placeItems: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <p className="lp-cuerpo">{error}</p>
          <button type="button" className="lp-boton" style={{ background: '#111827', color: '#fff', marginTop: '3vh', padding: '0 1.5rem' }} onClick={() => navigate('/clases')}>
            Volver a mis clases
          </button>
        </div>
      </div>
    );
  }

  if (!spec || !escena) {
    return (
      <div className="lesson-player" style={{ display: 'grid', placeItems: 'center' }}>
        <p className="lp-cuerpo">Preparando la clase…</p>
      </div>
    );
  }

  const question = spec.questions.find((q) => q.id === escena.data.question_ref);
  const densidad = esNivelInicial(spec.curriculum.grade_level) ? 'inicial' : 'estandar';

  return (
    <div
      className="lesson-player"
      data-densidad={densidad}
      ref={contenedor}
      lang="es-CL"
    >
      {/* El cambio de escena se anuncia a lectores de pantalla sin ocupar
          espacio en la proyección. */}
      <p
        aria-live="polite"
        style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}
      >
        Escena {indice + 1} de {total}: {escena.title}
      </p>

      <div ref={escenaRef} style={{ height: '100%' }}>
        <SceneRenderer
          scene={escena}
          assets={assets}
          question={question}
          revelados={revelados}
          respuestaVisible={respuestaVisible}
          seleccionada={seleccionada}
          onResponder={(optionId) => {
            // Se puede tocar la alternativa (pizarrón) o revelar desde el
            // control. Nunca se guarda la respuesta: ver privacy del spec.
            setSeleccionada(optionId);
            setRespuestaVisible(true);
          }}
        />
      </div>

      {narracionAbierta && (
        <aside className="lp-narracion">
          <h2>Lo que dices en voz alta</h2>
          <p>{escena.narration || 'Esta escena no trae guion.'}</p>
          {escena.teacher_note && (
            <>
              <h2>Nota para ti</h2>
              <p className="lp-narracion-nota">{escena.teacher_note}</p>
            </>
          )}
        </aside>
      )}

      <div className="lp-controles" data-visible={controlesVisibles}>
        <button type="button" className="lp-boton" onClick={retroceder} disabled={indice === 0 && revelados === 0} aria-label="Anterior">‹</button>
        <span className="lp-progreso" aria-hidden="true">{indice + 1}/{total}</span>
        <button type="button" className="lp-boton" onClick={avanzar} disabled={indice === total - 1 && revelados >= pasosTotales} aria-label="Siguiente">›</button>
        <button type="button" className="lp-boton" onClick={() => setNarracionAbierta((v) => !v)} aria-pressed={narracionAbierta} aria-label="Ver guion (tecla N)">N</button>
        <button type="button" className="lp-boton" onClick={pantallaCompleta} aria-label="Pantalla completa">⛶</button>
        <button type="button" className="lp-boton" onClick={salir} aria-label="Salir de la presentación">✕</button>
      </div>

      {!imagenesListas && (
        <p style={{ position: 'fixed', top: '2vh', right: '2vh', fontSize: '0.9rem', color: '#374151' }}>
          Cargando imágenes…
        </p>
      )}
    </div>
  );
}

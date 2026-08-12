import type { Asset, Question, Scene } from '../../types/lesson';

/** Imagen de escena con degradación real.
 *
 * Cuando el asset no está listo o falló, se muestra el `alt` como contenido en
 * vez de un hueco: en 1° y 2° básico la imagen es el contenido, así que una
 * escena sin figura tiene que seguir comunicando su idea.
 */
function Figura({ asset }: { asset: Asset | undefined }) {
  if (!asset) return null;
  if (asset.status === 'ready' && asset.uri) {
    return (
      <figure className="lp-figura">
        <img src={asset.uri} alt={asset.alt} />
      </figure>
    );
  }
  return (
    <div className="lp-figura">
      <p className="lp-figura-alt">{asset.alt}</p>
    </div>
  );
}

interface Props {
  scene: Scene;
  assets: Record<string, Asset>;
  question?: Question;
  /** Cuántos pasos del proceso se han revelado. */
  revelados: number;
  /** La respuesta correcta ya se mostró al curso. */
  respuestaVisible: boolean;
  onResponder: (optionId: string) => void;
  seleccionada: string;
}

export default function SceneRenderer({
  scene, assets, question, revelados, respuestaVisible, onResponder, seleccionada,
}: Props) {
  const figura = <Figura asset={assets[scene.asset_ids[0]]} />;

  switch (scene.type) {
    // Idea grande al costado de la imagen, con aire.
    case 'concept':
      return (
        <section className="lp-escena" aria-label={scene.title}>
          <div className="lp-concept">
            <div>
              <h1 className="lp-titulo">{scene.title}</h1>
              <p className="lp-cuerpo" style={{ marginTop: '3vh' }}>{scene.body}</p>
            </div>
            {figura}
          </div>
        </section>
      );

    // La imagen manda; el texto la subtitula.
    case 'example':
      return (
        <section className="lp-escena" aria-label={scene.title}>
          <h1 className="lp-titulo">{scene.title}</h1>
          <div className="lp-example">
            {figura}
            <p className="lp-cuerpo">{scene.body}</p>
            {scene.data.examples.length > 0 && (
              <ul className="lp-example-lista">
                {scene.data.examples.map((ej) => (
                  <li key={ej.id} className="lp-example-item">{ej.text}</li>
                ))}
              </ul>
            )}
          </div>
        </section>
      );

    // Progresión visible: los pasos se revelan de a uno.
    case 'process':
      return (
        <section className="lp-escena" aria-label={scene.title}>
          <h1 className="lp-titulo">{scene.title}</h1>
          <p className="lp-cuerpo">{scene.body}</p>
          <ol className="lp-pasos">
            {scene.data.steps.map((paso, i) => (
              <li key={paso.id} className="lp-paso" data-oculto={i >= revelados}>
                <span className="lp-paso-numero" aria-hidden="true">{i + 1}</span>
                <span className="lp-paso-label">{paso.label}</span>
                <span className="lp-paso-desc">{paso.description}</span>
              </li>
            ))}
          </ol>
        </section>
      );

    // Pregunta fija arriba; alternativas grandes, tocables y con imagen.
    case 'quiz':
      return (
        <section className="lp-escena" aria-label={scene.title}>
          <h1 className="lp-titulo">{question?.prompt || scene.title}</h1>
          <ul className="lp-alternativas">
            {question?.options.map((op) => {
              const esCorrecta = question.correct_option_ids.includes(op.id);
              const estado = !respuestaVisible
                ? (seleccionada === op.id ? 'elegida' : 'reposo')
                : esCorrecta ? 'correcta' : 'descartada';
              return (
                <li key={op.id} style={{ display: 'flex' }}>
                  <button
                    type="button"
                    className="lp-alternativa"
                    style={{ flex: 1 }}
                    data-estado={estado}
                    aria-pressed={seleccionada === op.id}
                    onClick={() => onResponder(op.id)}
                  >
                    <Figura asset={assets[op.asset_id]} />
                    <span>{op.label}</span>
                    {/* El color no es el único portador: también va la marca. */}
                    {respuestaVisible && esCorrecta && (
                      <span className="lp-alternativa-marca">✓ correcta</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
          {respuestaVisible && question?.explanation && (
            <p className="lp-explicacion">{question.explanation}</p>
          )}
        </section>
      );

    // Cierre visualmente distinto: se nota que la clase terminó.
    case 'recap':
      return (
        <section className="lp-escena" aria-label={scene.title}>
          <div className="lp-recap">
            <h1 className="lp-titulo">{scene.title}</h1>
            <ul className="lp-claves">
              {scene.data.key_points.map((punto) => (
                <li key={punto} className="lp-clave">{punto}</li>
              ))}
            </ul>
          </div>
        </section>
      );

    // Un tipo desconocido viene de un spec más nuevo que este player: se
    // muestra como tarjeta de texto en vez de romper la clase en plena sala.
    default:
      return (
        <section className="lp-escena" aria-label={scene.title}>
          <h1 className="lp-titulo">{scene.title}</h1>
          <p className="lp-cuerpo">{scene.body}</p>
        </section>
      );
  }
}

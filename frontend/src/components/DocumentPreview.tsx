import type { ReactNode } from 'react';
import { ArrowPathIcon, PhotoIcon } from '@heroicons/react/24/outline';
import type { DocumentContent } from '../types';

/** Renders **bold** / *italic* markdown as safe React nodes (no HTML injection). */
function renderInline(text: string): ReactNode {
  const parts: ReactNode[] = [];
  const regex = /(\*\*.+?\*\*|\*.+?\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    const token = match[0];
    parts.push(
      token.startsWith('**') ? (
        <strong key={key++}>{token.slice(2, -2)}</strong>
      ) : (
        <em key={key++}>{token.slice(1, -1)}</em>
      )
    );
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

function getItemText(item: any): string {
  return item.text || item.question || item.activity || item.description || item.content || item.title || '';
}

function getItemImageWords(item: any): string[] {
  if (item && typeof item === 'object' && Array.isArray(item.image_words)) {
    return item.image_words.map((w: string) => w.toLowerCase().trim()).filter((w: string) => w.length > 1);
  }
  return [];
}

interface ImageGridProps {
  words: string[];
  activityImages: Record<string, string>;
  loading?: boolean;
}

function ImageGrid({ words, activityImages, loading }: ImageGridProps) {
  if (!words.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-3 justify-center">
      {words.map(word => {
        const imgUrl = activityImages[word];
        return (
          <div key={word} className="text-center">
            {imgUrl ? (
              <img src={imgUrl} alt={word} className="w-24 h-24 object-cover rounded-lg border border-gray-200 mx-auto shadow-sm" />
            ) : (
              <div className="w-24 h-24 bg-gray-100 rounded-lg border border-dashed border-gray-300 flex items-center justify-center">
                {loading ? (
                  <ArrowPathIcon className="w-4 h-4 text-gray-300 animate-spin" />
                ) : (
                  <PhotoIcon className="w-6 h-6 text-gray-300" />
                )}
              </div>
            )}
            <p className="text-xs text-gray-600 mt-1 capitalize font-medium">{word}</p>
          </div>
        );
      })}
    </div>
  );
}

interface SectionProps {
  section: any;
  activityImages: Record<string, string>;
  activityImagesLoading?: boolean;
}

function Section({ section, activityImages, activityImagesLoading }: SectionProps) {
  const content = section.content;
  return (
    <div className="mb-6">
      {section.title && (
        <h3 className="text-base font-semibold text-gray-900 mb-2 border-b border-gray-300 pb-1">{section.title}</h3>
      )}
      {typeof content === 'string' && (
        <p className="text-sm text-gray-900 whitespace-pre-line">{renderInline(content)}</p>
      )}
      {Array.isArray(content) &&
        content.map((item: any, i: number) => {
          const imgWords = getItemImageWords(item);
          return (
            <div key={i} className="mb-3">
              {typeof item === 'string' ? (
                <p className="text-sm text-gray-900">
                  {i + 1}. {renderInline(item)}
                </p>
              ) : (
                <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                  <p className="text-sm font-medium text-gray-900">
                    {item.number || i + 1}. {renderInline(getItemText(item))}
                    {item.points && <span className="ml-2 text-xs text-gray-600">({item.points} pts)</span>}
                  </p>
                  <ImageGrid words={imgWords} activityImages={activityImages} loading={activityImagesLoading} />
                  {item.options && (
                    <ul className="mt-2 space-y-1 ml-4">
                      {item.options.map((opt: string, j: number) => (
                        <li key={j} className="text-sm text-gray-800">
                          {String.fromCharCode(65 + j)}) {opt}
                        </li>
                      ))}
                    </ul>
                  )}
                  {item.answer && <p className="mt-1 text-xs text-emerald-600 font-medium">✓ {item.answer}</p>}
                </div>
              )}
            </div>
          );
        })}
    </div>
  );
}

interface DocumentPreviewProps {
  id?: string;
  content: DocumentContent;
  imageUrl?: string | null;
  imageLoading?: boolean;
  activityImages?: Record<string, string>;
  activityImagesLoading?: boolean;
  showStudentRow?: boolean;
  className?: string;
  /** Skip the white card chrome (border/shadow/padding) when already inside another container, e.g. a dialog. */
  bare?: boolean;
}

export default function DocumentPreview({
  id,
  content,
  imageUrl,
  imageLoading,
  activityImages = {},
  activityImagesLoading,
  showStudentRow = false,
  className = '',
  bare = false,
}: DocumentPreviewProps) {
  // Always keep the white/dark-text page surface — this previews a printed document,
  // not app chrome, so it must stay legible even inside a dark-themed dialog.
  const chrome = `bg-white text-gray-900 rounded-2xl p-4 sm:p-8 print-content ${bare ? '' : 'shadow-sm border border-gray-200'}`;
  return (
    <div id={id} className={`${chrome} ${className}`}>
      <div className="text-center mb-6 pb-4 border-b-2 border-gray-900">
        <h1 className="text-lg sm:text-xl font-bold text-gray-900 uppercase">{content.title}</h1>
        {content.metadata && (
          <div className="flex flex-wrap justify-center gap-x-6 gap-y-1 mt-2 text-sm text-gray-700 font-medium">
            <span>
              <strong>Asignatura:</strong> {content.metadata.subject}
            </span>
            <span>
              <strong>Nivel:</strong> {content.metadata.grade}
            </span>
            {content.metadata.total_points && (
              <span>
                <strong>Puntaje:</strong> {content.metadata.total_points} pts
              </span>
            )}
          </div>
        )}
        {showStudentRow && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-4 mt-4 text-left border border-gray-300 rounded p-3">
            <div className="text-sm">
              <strong>Nombre:</strong> _________________
            </div>
            <div className="text-sm">
              <strong>Curso:</strong> _______________
            </div>
            <div className="text-sm">
              <strong>Fecha:</strong> _______________
            </div>
          </div>
        )}
      </div>

      {imageLoading && (
        <div className="mb-4 flex justify-center items-center gap-2 text-sm text-gray-400">
          <ArrowPathIcon className="w-4 h-4 animate-spin" />
          Generando ilustración...
        </div>
      )}
      {!imageLoading && imageUrl && (
        <div className="mb-4 flex justify-center">
          <img
            src={imageUrl}
            alt="Ilustración generada por IA"
            className="max-h-48 rounded-lg border border-gray-200"
            onError={e => {
              (e.target as HTMLImageElement).style.display = 'none';
            }}
          />
        </div>
      )}

      {content.instructions && (
        <div className="mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
          <p className="text-sm text-gray-900">
            <strong>Instrucciones:</strong> {content.instructions}
          </p>
        </div>
      )}

      {content.sections?.map((section: any, idx: number) => (
        <Section key={idx} section={section} activityImages={activityImages} activityImagesLoading={activityImagesLoading} />
      ))}
    </div>
  );
}

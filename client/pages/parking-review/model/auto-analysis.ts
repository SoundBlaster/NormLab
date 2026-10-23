import { narrativeRoute, type NarrativeContext } from './contracts.js';

export type AutoAnalysisBlocker = { message: string; target?: 'context' };
type State = {
  working: boolean;
  legalUnsaved: boolean;
  historical: boolean;
  narrativeChanged: boolean;
  addingStatement: boolean;
  saveError: boolean;
  unsaved: boolean;
  jobRunning: boolean;
  extractorAvailable: boolean;
  contextProposalAvailable?: boolean;
  context: NarrativeContext;
  hasStatements: boolean;
  replaceApproved: boolean;
};

/** The visible next step and the disabled state share one readiness decision. */
export function autoAnalysisBlocker(state: State): AutoAnalysisBlocker | undefined {
  if (state.working) return { message: 'Дождитесь завершения текущей операции.' };
  if (state.legalUnsaved)
    return {
      message: 'Сохраните или отмените правки в разделе «Юридические обстоятельства и расчёт».',
    };
  if (state.historical)
    return {
      message:
        'Откройте актуальную ревизию кнопкой выше. Историческая ревизия доступна только для чтения.',
    };
  if (state.narrativeChanged)
    return { message: 'Текст события изменён. Создайте для него новый черновик в разделе 01.' };
  if (state.addingStatement)
    return { message: 'Завершите или отмените добавление нового утверждения ниже.' };
  if (state.saveError)
    return { message: 'Сохранение ревизии не подтверждено. Сначала повторите сохранение вручную.' };
  if (state.unsaved)
    return {
      message:
        'Дождитесь сохранения изменений. Если оно не начинается, заполните обязательные поля и нажмите «Сохранить сейчас».',
    };
  if (state.jobRunning)
    return { message: 'Авторазбор уже выполняется. Его состояние показано ниже.' };
  if (!state.extractorAvailable)
    return {
      message: 'Авторазбор на сервере не настроен. Можно добавить утверждения вручную ниже.',
    };
  const route = narrativeRoute(state.context);
  if (route !== 'parking-review') {
    const messages = {
      clarify: state.contextProposalAvailable
        ? 'В разделе 02 нажмите «Предложить контекст по тексту». Проверьте предложение и подтвердите контекст; ручной выбор также доступен.'
        : 'В разделе 02 выберите тему «Парковка», парковочный контекст и характер «Конкретный эпизод», затем подтвердите контекст.',
      'other-topic':
        'Для выбранной темы авторазбор в парковочном пилоте недоступен. Проверьте контекст обращения.',
      'not-a-case':
        'Для авторазбора нужен конкретный эпизод. Проверьте текст и характер обращения в разделе 02.',
      'choose-episode':
        'В тексте несколько эпизодов. Выделите один в новый черновик перед авторазбором.',
    };
    return { message: messages[route], target: 'context' };
  }
  if (state.context.decision !== 'confirmed')
    return {
      message:
        'Сначала нажмите «Подтвердить контекст» в разделе 02. После сохранения подтверждения авторазбор станет доступен.',
      target: 'context',
    };
  if (state.hasStatements && !state.replaceApproved)
    return {
      message:
        'Для повторного разбора разрешите замену текущей разметки галочкой ниже. Прежняя ревизия останется в истории.',
    };
  return undefined;
}

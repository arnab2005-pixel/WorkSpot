import en from "./locales/en.json";
import bn from "./locales/bn.json";
import hi from "./locales/hi.json";
import mr from "./locales/mr.json";
import ta from "./locales/ta.json";
import te from "./locales/te.json";
import kn from "./locales/kn.json";
import ml from "./locales/ml.json";
import gu from "./locales/gu.json";
import pa from "./locales/pa.json";
import or from "./locales/or.json";
import as from "./locales/as.json";
import bho from "./locales/bho.json";
import mai from "./locales/mai.json";
import ur from "./locales/ur.json";
import { getLanguageConfig } from "./languageConfig";

const locales: Record<string, typeof en> = { en, bn, hi, mr, ta, te, kn, ml, gu, pa, or, as, bho, mai, ur };

export function getLocaleCopy(language: string, fallback: Record<string, any>) {
  const locale = locales[getLanguageConfig(language).code] ?? en;
  return {
    ...fallback,
    nav: [locale.navigation.home, locale.navigation.profile, locale.navigation.opportunities, locale.navigation.ai, locale.navigation.progress, locale.navigation.notifications],
    continue: locale.common.continue,
    listen: locale.common.listen,
    send: locale.common.send,
    profile: locale.navigation.profile,
    opportunities: locale.navigation.opportunities,
    advisor: locale.navigation.ai,
    progress: locale.navigation.progress,
    help: locale.navigation.help,
    type: fallback.type,
    speak: locale.voice.speakIn
  };
}

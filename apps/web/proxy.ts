import createMiddleware from "next-intl/middleware";
import {routing} from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // Match only page requests; exclude internal assets, APIs, sitemap/robots.
  matcher: ["/((?!api|_next|sitemap.xml|robots.txt|.*\\.[\\w]+$).*)"],
};

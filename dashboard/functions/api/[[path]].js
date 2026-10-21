import { proxy } from "../_shared/proxy.js";
export const onRequest = ({ request, env }) => proxy(request, env, "api");

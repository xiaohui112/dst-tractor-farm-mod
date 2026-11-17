/* Host bindings only. Planning runs in the unmodified Mod Lua modules. */
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <emscripten.h>
#include "lua.h"
#include "lauxlib.h"
#include "lualib.h"

static char *output;
static int failed;
EM_JS(void, report_phase, (const char *text), {
  if (Module.onPhase) Module.onPhase(UTF8ToString(text));
});
static float f32(double x) { volatile float value = (float)x; return value; }
static int number_f32(lua_State *L) {
  lua_pushnumber(L, f32(luaL_checknumber(L, 1))); return 1;
}
static int distance_sq(lua_State *L) {
  float dx=f32(f32(luaL_checknumber(L,1))-f32(luaL_checknumber(L,4)));
  float dy=f32(f32(luaL_checknumber(L,2))-f32(luaL_checknumber(L,5)));
  float dz=f32(f32(luaL_checknumber(L,3))-f32(luaL_checknumber(L,6)));
  lua_pushnumber(L,f32(f32(dz*dz)+f32(f32(dx*dx)+f32(dy*dy)))); return 1;
}
static int radius_sq(lua_State *L) {
  float r=f32(luaL_checknumber(L,1)); lua_pushnumber(L,f32(r*r)); return 1;
}
static int phase(lua_State *L) { report_phase(luaL_checkstring(L,1)); return 0; }
static int cancelled(lua_State *L) { lua_pushboolean(L,0); return 1; }
static int clock_now(lua_State *L) { lua_pushnumber(L,emscripten_get_now()/1000.0); return 1; }
static void bind(lua_State *L,const char *name,lua_CFunction fn) {
  lua_pushcfunction(L,fn); lua_setglobal(L,name);
}
EMSCRIPTEN_KEEPALIVE const char *planner_execute(const char *script) {
  free(output); output=NULL; failed=0;
  lua_State *L=luaL_newstate();
  if (!L) { failed=1; output=strdup("无法创建 Lua 环境：内存不足。"); return output; }
  luaL_openlibs(L);
  bind(L,"PY_F32",number_f32); bind(L,"PY_DISTANCE_SQ",distance_sq);
  bind(L,"PY_RADIUS_SQ",radius_sq); bind(L,"PY_PHASE",phase);
  bind(L,"PY_CANCELLED",cancelled);
  lua_getglobal(L,"os"); lua_pushcfunction(L,clock_now); lua_setfield(L,-2,"clock"); lua_pop(L,1);
  if (luaL_loadstring(L,script) || lua_pcall(L,0,1,0)) failed=1;
  const char *value=lua_tostring(L,-1);
  output=strdup(value ? value : "Lua 未返回有效结果。");
  lua_close(L); return output;
}
EMSCRIPTEN_KEEPALIVE int planner_failed(void) { return failed; }

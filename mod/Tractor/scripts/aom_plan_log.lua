-- 规划专用追加日志。正常记录不经过print，避免混入master/client日志。
local M={}
local root,configured_path,selected_path,enabled,last_error
local function FileName()
 local cave=TheWorld and (TheWorld.prefab=='cave' or TheWorld.HasTag and TheWorld:HasTag('cave'))
 return cave and 'tractor_giant_planning_caves.log' or 'tractor_giant_planning_master.log'
end
local function Candidates()
 if configured_path then return {configured_path}end
 local out={};local home=os.getenv and os.getenv('HOME');local profile=os.getenv and os.getenv('USERPROFILE')
 if home then
  out[#out+1]=home..'/Documents/Klei/DoNotStarveTogether/'..FileName()
  out[#out+1]=home..'/.klei/DoNotStarveTogether/'..FileName()
 end
 if profile then out[#out+1]=profile..'/Documents/Klei/DoNotStarveTogether/'..FileName()end
 if root then out[#out+1]=root..FileName()end
 return out
end
function M.Configure(modroot,path)
 root=type(modroot)=='string' and modroot or nil;configured_path=path;selected_path=nil;last_error=nil
 -- 离线地图桩未配置真实引擎时不写玩家的游戏目录；测试可显式指定临时文件。
 enabled=path~=nil or root~=nil and TheSim and TheSim.GetRealTime~=nil
end
function M.Path()
 if not enabled then return nil end
 if selected_path then return selected_path end
 if not io or not io.open then last_error='file_io_unavailable';return nil end
 for _,path in ipairs(Candidates())do
  local ok,file,err=pcall(io.open,path,'a')
  if ok and file then
   local closed,reason=pcall(file.close,file)
   if closed then selected_path=path;return path end
   last_error=tostring(reason)
  else last_error=ok and tostring(err) or tostring(file)end
 end
 return nil
end
function M.Append(entry)
 if not enabled then return true end -- 非游戏离线运行不产生规划日志。
 local path=M.Path();if not path then return false,last_error end
 local ok,result,err=pcall(function()
  local file,reason=io.open(path,'a');if not file then return false,reason end
  local written,message=file:write(entry,'\n')
  local closed,close_error=file:close()
  if not written then return false,message end
  if not closed then return false,close_error end
  return true
 end)
 if not ok then last_error=tostring(result);return false,last_error end
 if not result then last_error=tostring(err);return false,last_error end
 last_error=nil;return true
end
function M.Error()return last_error end
return M

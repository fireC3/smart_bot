import { useEffect, useRef } from "react";
import * as PIXI from "pixi.js";
import { Live2DModel } from "pixi-live2d-display/cubism4";
import styles from "./Live2DView.module.css";
import {useAppAction, AppAction} from "../utils/sortcut.ts";
let registered = false;

export default function Live2DView({ modelUrl }: { modelUrl: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const modelRef = useRef<Live2DModel | null>(null);
  const appRef = useRef<PIXI.Application | null>(null);

  useAppAction( AppAction.TOGGLE_CHAT_HISTORY, () => {
    console.log("重置模型");
  });


  useEffect(() => {
    if (!containerRef.current) return;

    if (!registered) {
      Live2DModel.registerTicker(PIXI.Ticker as any);
      registered = true;
    }

    const app = new PIXI.Application({
      width: window.innerWidth,
      height: window.innerHeight,
      backgroundAlpha: 0,
      antialias: true,
      autoDensity: true,
      resolution: window.devicePixelRatio || 1,
    });
    appRef.current = app;
    app.stage.eventMode = "none";
    (app.view as HTMLCanvasElement).style.pointerEvents = "none";
    containerRef.current.appendChild(app.view as HTMLCanvasElement);

    let disposed = false;

    (async () => {
      const model = await Live2DModel.from(modelUrl, { autoInteract: false });
      if (disposed) return;

      model.anchor.set(0.5, 0.5);
      model.scale.set(0.18);
      app.stage.addChild(model as any);
      modelRef.current = model;

      // 2. 监听容器变化，仅移动模型坐标
      const resizeObserver = new ResizeObserver((entries) => {
        if (!entries[0] || !modelRef.current) return;
        
        // 获取当前容器相对于视口的坐标
        const rect = entries[0].target.getBoundingClientRect();
        
        // 计算容器的中心点在全屏 Canvas 下的 X 坐标
        // 比如左侧区域占了 60% 宽度，那中心就是 window.innerWidth * 0.6 / 2
        const centerX = rect.left + rect.width / 2;
        
        // 直接移动模型位置 (这是 Canvas 移动元素的正统做法)
        modelRef.current.x = centerX;
        modelRef.current.y = rect.bottom; // 底部对齐
      });

      resizeObserver.observe(containerRef.current!);
    })();

    // 处理窗口缩放，同步画布最大尺寸
    const handleWindowResize = () => {
      app.renderer.resize(window.innerWidth, window.innerHeight);
    };
    window.addEventListener('resize', handleWindowResize);

    return () => {
      disposed = true;
      window.removeEventListener('resize', handleWindowResize);
      app.destroy(true, { children: true });
    };
  }, [modelUrl]);

  return <div ref={containerRef} className={styles.root} />;
}
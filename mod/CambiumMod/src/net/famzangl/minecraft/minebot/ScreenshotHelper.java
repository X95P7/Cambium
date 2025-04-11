
package net.famzangl.minecraft.minebot;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiScreen;
import net.minecraft.util.ScreenShotHelper;
import java.io.File;

public class ScreenshotHelper {

    public static void takeScreenshot() {
        GuiScreen currentScreen = Minecraft.getMinecraft().currentScreen;
        Minecraft mc = Minecraft.getMinecraft();
        System.out.println("Taking screenshot...");
        File screenshotsDir = new File(mc.mcDataDir, "headlessScreenshots");
        ScreenShotHelper.saveScreenshot(screenshotsDir, mc.getFramebuffer());
    }
}


package net.famzangl.minecraft.minebot;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiScreen;
import net.minecraft.util.ScreenShotHelper;
import java.io.File;

import net.minecraft.client.Minecraft;
import net.minecraft.client.shader.Framebuffer;
import net.minecraft.util.ScreenShotHelper;

import java.io.File;

public class ScreenshotHelper {
    private final Minecraft mc;

    public ScreenshotHelper() {
        this.mc = Minecraft.func_71410_x();
    }

    public void takeScreenshot() {
        // Path to save screenshots inside the container (maps to C:\Cambium\screenshots on host)
        File screenshotDir = new File("/screenshots");

        // Ensure the directory exists
        if (!screenshotDir.exists()) {
            boolean created = screenshotDir.mkdirs();
            if (!created) {
                System.err.println("Failed to create screenshot directory!");
                return;
            }
        }
    
        // Get the current framebuffer
        Framebuffer framebuffer = mc.func_147110_a();
    
        // Save the screenshot in the desired directory
        ScreenShotHelper.func_148260_a(screenshotDir, mc.field_71443_c, mc.field_71440_d, framebuffer);
    }
}


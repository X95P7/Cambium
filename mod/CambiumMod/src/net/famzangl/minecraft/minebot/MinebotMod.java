/*******************************************************************************
 * This file is part of Minebot.
 *
 * Minebot is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Minebot is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Minebot.  If not, see <http://www.gnu.org/licenses/>.
 *******************************************************************************/
package net.famzangl.minecraft.minebot;

import java.net.URISyntaxException;

import net.famzangl.minecraft.minebot.ai.AIController;
import net.famzangl.minecraft.minebot.ai.ChatListener;
import net.famzangl.minecraft.minebot.ai.DeathListener;
import net.famzangl.minecraft.minebot.ai.path.world.BlockBoundsCache;
import net.famzangl.minecraft.minebot.ai.strategy.cambium.LeftClickStrategy;
import net.minecraftforge.client.event.ClientChatReceivedEvent;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.FMLCommonHandler;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.common.Mod.EventHandler;
import net.minecraftforge.fml.common.Mod.Instance;
import net.minecraftforge.fml.common.event.FMLInitializationEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.LoggerContext;
import org.apache.logging.log4j.core.config.Configuration;
import net.minecraftforge.fml.common.event.FMLInitializationEvent;

@Mod(modid = "minebot-mod", name = "Minebot", version = "0.4")
public class MinebotMod {
	@Instance(value = "minebot-mod")
	public static MinebotMod instance;
	
	static {
		// logging
		String doLogging = System.getProperty("MINEBOT_LOG", "0");
		if (doLogging.equals("1")) {
			LoggerContext context = (LoggerContext) LogManager.getContext(false);
			Configuration config = context.getConfiguration();
			try {
				context.setConfigLocation(MinebotMod.class.getResource("log4j.xml").toURI());
			} catch (URISyntaxException e) {
				e.printStackTrace();
			}
		}
	}
	
	// Note: 6364136223846793005L * 0xc097ef87329e28a5l = 1
	
	@EventHandler
	public void init(FMLInitializationEvent event) {

		BlockBoundsCache.initialize();
		FMLCommonHandler.instance().bus().register(new PlayerUpdateHandler());
		final AIController controller = AIController.getInstance();
		controller.initialize();
		controller.getMinecraft().gameSettings.pauseOnLostFocus = false;
		MinecraftForge.EVENT_BUS.register(new ChatListener());
		MinecraftForge.EVENT_BUS.register(new DeathListener());
	}

	public static String getVersion() {
		return MinebotMod.class.getAnnotation(Mod.class).version();
	}

}

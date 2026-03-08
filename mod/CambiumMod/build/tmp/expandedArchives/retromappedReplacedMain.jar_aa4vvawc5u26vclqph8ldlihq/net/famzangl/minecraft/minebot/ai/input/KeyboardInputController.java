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
package net.famzangl.minecraft.minebot.ai.input;

import net.minecraft.client.Minecraft;
import net.minecraft.client.settings.GameSettings;
import net.minecraft.client.settings.KeyBinding;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.logging.log4j.Marker;
import org.apache.logging.log4j.MarkerManager;

/**
 * This class simulates a key pressed / not pressed.
 * 
 * @author Michael Zangl
 *
 */
public class KeyboardInputController {
	private static final Marker MARKER_KEY = MarkerManager.getMarker("key");
	private static final Logger LOGGER = LogManager
			.getLogger(KeyboardInputController.class);

	private static abstract class KeyAdapter {

		public abstract KeyBinding get(GameSettings gameSettings);
	}

	public enum KeyType {
		ATTACK(501, new KeyAdapter() {
			@Override
			public KeyBinding get(GameSettings gameSettings) {
				return gameSettings.field_74312_F;
			}
		}), USE(502, new KeyAdapter() {
			@Override
			public KeyBinding get(GameSettings gameSettings) {
				return gameSettings.field_74313_G;
			}
		}), SNEAK(503, new KeyAdapter() {
			@Override
			public KeyBinding get(GameSettings gameSettings) {
				return gameSettings.field_74311_E;
			}
		}), SPRINT(504, new KeyAdapter() {
			@Override
			public KeyBinding get(GameSettings gameSettings) {
				return gameSettings.field_151444_V;
			}
		}), JUMP(504, new KeyAdapter() {
			@Override
			public KeyBinding get(GameSettings gameSettings) {
				return gameSettings.field_74314_A;
			}
		});

		private final KeyAdapter keyAdapter;
		private int keyCode;

		private KeyType(int keyCode, KeyAdapter keyAdapter) {
			this.keyCode = keyCode;
			this.keyAdapter = keyAdapter;
		}

		public KeyBinding getBinding(Minecraft mc) {
			return keyAdapter.get(mc.field_71474_y);
		}
	}

	private Minecraft mc;
	private KeyType key;
	private boolean isOverride;
	private int oldKeyCode;
	private boolean wasOverride;

	public KeyboardInputController(Minecraft mc, KeyType key) {
		this.mc = mc;
		this.key = key;
		oldKeyCode = key.getBinding(mc).func_151469_h();
	}

	/**
	 * Called if the button press should be simulated on the next tick.
	 */
	public void overridePressed() {
		LOGGER.info(MARKER_KEY, "Requested key press for " + key);
		if (isOverride) {
			LOGGER.warn(MARKER_KEY, "A key press was requested twice for " + key);
		}
		isOverride = true;
	}

	public void doTick() {
		KeyBinding binding = key.getBinding(mc);
		if (isOverride) {
			if (!wasOverride) {
				LOGGER.trace(MARKER_KEY, "Simulate a key press down for " + key);
				// Map to a temporary key
				binding.func_151462_b(key.keyCode);
				KeyBinding.func_74508_b();
				// Simulate press of that key.
				KeyBinding.func_74510_a(key.keyCode, true);
				KeyBinding.func_74507_a(key.keyCode);
			} else {
				LOGGER.trace(MARKER_KEY, "Key should still be down. " + key);
			}
			if (!binding.func_151468_f()) {
				LOGGER.error(MARKER_KEY, "Key press simulated but key is not pressed: " + key);
			}
		} else {
			if (wasOverride) {
				LOGGER.trace(MARKER_KEY, "Key ovveride deactivated: " + key);
				KeyBinding.func_74510_a(key.keyCode, false);
				binding.func_151462_b(oldKeyCode);
				KeyBinding.func_74508_b();
			}
		}
		wasOverride = isOverride;
		isOverride = false;
	}

	public boolean wasPressedByUser() {
		return !isOverride && !wasOverride && key.getBinding(mc).func_151470_d();
	}
}

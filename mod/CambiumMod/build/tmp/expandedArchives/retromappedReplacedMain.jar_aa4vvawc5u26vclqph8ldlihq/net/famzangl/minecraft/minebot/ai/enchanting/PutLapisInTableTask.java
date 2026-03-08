package net.famzangl.minecraft.minebot.ai.enchanting;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.strategy.TintStrategy;
import net.famzangl.minecraft.minebot.ai.task.inventory.PutItemInContainerTask;
import net.minecraft.client.gui.GuiEnchantment;
import net.minecraft.inventory.Slot;
import net.minecraft.item.EnumDyeColor;
import net.minecraft.item.ItemStack;

/**
 * Put the lapis into the enchantment table.
 * 
 * @author michael
 *
 */
public class PutLapisInTableTask extends PutItemInContainerTask {

	private static final int TABLE_INV_OFFSET = 2;

	@Override
	protected int getStackToPut(AIHelper h) {
		final GuiEnchantment screen = (GuiEnchantment) h.getMinecraft().field_71462_r;
		for (int i = TABLE_INV_OFFSET; i < 9 * 4 + TABLE_INV_OFFSET; i++) {
			final Slot slot = screen.field_147002_h.func_75139_a(i);
			if (slot == null || !slot.func_82869_a(h.getMinecraft().field_71439_g)) {
				continue;
			}
			final ItemStack stack = slot.func_75211_c();
			if (new TintStrategy.DyeItemFilter(EnumDyeColor.BLUE)
					.matches(stack)) {
				return i;
			}
		}
		return -1;
	}
}

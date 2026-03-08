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
package net.famzangl.minecraft.minebot.ai.scanner;

import net.minecraft.init.Blocks;
import net.minecraft.init.Items;
import net.minecraft.item.Item;

/**
 * Helper utility to group blocks.
 * TODO: Implement a strategy for this.
 * @author michael
 *
 */
public class ItemGrouper {
	public static class ItemGroup {
		private final Item fromItem;
		private final Item toItem;
		private final int size; // 2 or 3
		public ItemGroup(Item fromItem, Item toItem, int size) {
			super();
			this.fromItem = fromItem;
			this.toItem = toItem;
			this.size = size;
		}
		
	}
	
	public static ItemGroup[] ITEM_GROUPS = new ItemGroup[] {
		new ItemGroup(Items.field_151015_O, Item.func_150898_a(Blocks.field_150407_cf), 3),
		new ItemGroup(Items.field_151044_h, Item.func_150898_a(Blocks.field_150402_ci), 3),
		new ItemGroup(Items.field_151137_ax, Item.func_150898_a(Blocks.field_150451_bX), 3),
		new ItemGroup(Items.field_151166_bC, Item.func_150898_a(Blocks.field_150475_bE), 3),
		new ItemGroup(Items.field_151045_i, Item.func_150898_a(Blocks.field_150484_ah), 3),
		new ItemGroup(Items.field_151042_j, Item.func_150898_a(Blocks.field_150339_S), 3),
		new ItemGroup(Items.field_151043_k, Item.func_150898_a(Blocks.field_150340_R), 3),
		new ItemGroup(Items.field_151074_bl, Items.field_151043_k, 3),
	//	new ItemGroup(Items.snowball, Item.getItemFromBlock(Blocks.snow), 2),
	};
}

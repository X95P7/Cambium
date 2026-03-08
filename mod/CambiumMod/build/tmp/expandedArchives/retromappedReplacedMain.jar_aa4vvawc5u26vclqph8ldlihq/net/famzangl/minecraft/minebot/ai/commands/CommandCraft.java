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
package net.famzangl.minecraft.minebot.ai.commands;

import net.famzangl.minecraft.minebot.ai.AIHelper;
import net.famzangl.minecraft.minebot.ai.command.AICommand;
import net.famzangl.minecraft.minebot.ai.command.AICommandInvocation;
import net.famzangl.minecraft.minebot.ai.command.AICommandParameter;
import net.famzangl.minecraft.minebot.ai.command.AICommandParameter.BlockFilter;
import net.famzangl.minecraft.minebot.ai.command.BlockWithDataOrDontcare;
import net.famzangl.minecraft.minebot.ai.command.ParameterType;
import net.famzangl.minecraft.minebot.ai.path.world.BlockSet;
import net.famzangl.minecraft.minebot.ai.path.world.BlockSets;
import net.famzangl.minecraft.minebot.ai.strategy.AIStrategy;
import net.famzangl.minecraft.minebot.ai.strategy.CraftStrategy;
import net.minecraft.init.Blocks;

@AICommand(helpText = "Crafts items of the given type.", name = "minebot")
public class CommandCraft {

	/**
	 * Blocks that can not be crafted.
	 */
	private static final BlockSet simpleBlocks = new BlockSet(
			Blocks.field_150350_a, Blocks.field_150382_bo, Blocks.field_150324_C, Blocks.field_150388_bm,
			Blocks.field_150383_bp, Blocks.field_150457_bL, Blocks.field_150464_aj, Blocks.field_150436_aH,
			Blocks.field_150414_aQ, Blocks.field_150465_bP, Blocks.field_150332_K,
			Blocks.field_180384_M, Blocks.field_150439_ay,
			Blocks.field_150416_aS, Blocks.field_150393_bb, Blocks.field_150472_an,
			Blocks.field_150455_bV, Blocks.field_150473_bD,
			Blocks.field_150374_bv, Blocks.field_150394_bc,
			Blocks.field_150437_az, Blocks.field_150441_bU,
			Blocks.field_150488_af, Blocks.field_150444_as, Blocks.field_150413_aR,
			Blocks.field_150454_av, Blocks.field_150325_L).unionWith(BlockSets.WOODEN_DOR).invert();

	public static final class MyBlockFilter extends BlockFilter {
		@Override
		public boolean matches(BlockWithDataOrDontcare b) {
			return simpleBlocks.contains(b);
		}
	}

	@AICommandInvocation()
	public static AIStrategy run(
			AIHelper helper,
			@AICommandParameter(type = ParameterType.FIXED, fixedName = "craft", description = "") String nameArg,
			@AICommandParameter(type = ParameterType.NUMBER, description = "Item count") int itemCount,
			@AICommandParameter(type = ParameterType.BLOCK_NAME, description = "Block", blockFilter = MyBlockFilter.class) BlockWithDataOrDontcare itemType) {
		return new CraftStrategy(itemCount, itemType);
	}

	@AICommandInvocation()
	public static AIStrategy run(
			AIHelper helper,
			@AICommandParameter(type = ParameterType.FIXED, fixedName = "craft", description = "") String nameArg,
			@AICommandParameter(type = ParameterType.NUMBER, description = "Item count") int itemCount,
			@AICommandParameter(type = ParameterType.NUMBER, description = "Item type") int itemType,
			@AICommandParameter(type = ParameterType.NUMBER, description = "Item subtype", optional = true) Integer itemSubtype) {
		return new CraftStrategy(itemCount, itemType, itemSubtype == null ? 0 : itemSubtype);
	}
}

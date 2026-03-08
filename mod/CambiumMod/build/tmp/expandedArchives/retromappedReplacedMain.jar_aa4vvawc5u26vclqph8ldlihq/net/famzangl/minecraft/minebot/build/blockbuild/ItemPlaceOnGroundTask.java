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
package net.famzangl.minecraft.minebot.build.blockbuild;

import net.famzangl.minecraft.minebot.ai.BlockItemFilter;
import net.famzangl.minecraft.minebot.ai.ItemFilter;
import net.famzangl.minecraft.minebot.ai.path.world.BlockSet;
import net.minecraft.block.Block;
import net.minecraft.init.Blocks;
import net.minecraft.util.BlockPos;

public class ItemPlaceOnGroundTask extends BuildFlatOnGroundTask {

	public static final BlockSet BLOCKS = new BlockSet(Blocks.field_150346_d,
			Blocks.field_150348_b, Blocks.field_150347_e, Blocks.field_150461_bJ, Blocks.field_150342_X,
			Blocks.field_150336_V, Blocks.field_150414_aQ, Blocks.field_150402_ci,
			Blocks.field_150365_q, Blocks.field_150462_ai, Blocks.field_150484_ah,
			Blocks.field_150482_ag, Blocks.field_150475_bE, Blocks.field_150412_bA,
			Blocks.field_150377_bs, Blocks.field_150359_w, Blocks.field_150340_R, Blocks.field_150352_o,
			Blocks.field_150349_c, Blocks.field_150351_n, Blocks.field_150407_cf, Blocks.field_150339_S,
			Blocks.field_150366_p, Blocks.field_150368_y, Blocks.field_150369_x,
			Blocks.field_150440_ba, Blocks.field_150341_Y, Blocks.field_150385_bj,
			Blocks.field_150424_aL, Blocks.field_150343_Z, Blocks.field_150423_aK,
			Blocks.field_150371_ca, Blocks.field_150449_bY, Blocks.field_150419_aX,
			Blocks.field_150451_bX, Blocks.field_150379_bu, Blocks.field_150450_ax,
			Blocks.field_150354_m, Blocks.field_150417_aV, Blocks.field_150335_W);
	private final Block block;

	protected ItemPlaceOnGroundTask(BlockPos forPosition, Block block) {
		super(forPosition);
		this.block = block;
	}

	@Override
	public ItemFilter getRequiredItem() {
		return new BlockItemFilter(block);
	}

	@Override
	public BuildTask withPositionAndRotation(BlockPos add, int rotateSteps,
			MirrorDirection mirror) {
		return new ItemPlaceOnGroundTask(add, block);
	}

	@Override
	public String toString() {
		return "ItemPlaceOnGroundTask [block=" + block + "]";
	}
}

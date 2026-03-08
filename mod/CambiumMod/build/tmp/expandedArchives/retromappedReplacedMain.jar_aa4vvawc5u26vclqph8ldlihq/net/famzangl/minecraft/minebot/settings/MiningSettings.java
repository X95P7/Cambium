package net.famzangl.minecraft.minebot.settings;

import net.famzangl.minecraft.minebot.ai.path.world.BlockFloatMap;
import net.minecraft.init.Blocks;

@MinebotSettingObject
public class MiningSettings {
	@ClampedFloat(min = 0, max = 1)
	private float randomness = 0.05f;

	@ClampedFloat(min = 0, max = 10)
	private float doubleBonus = 2;

	@ConstrainedBlockFloat(defaultValue = 1, min = 0, max = 10)
	private BlockFloatMap factorMap = new BlockFloatMap();

	@ConstrainedBlockFloat(defaultValue = 1, min = 0, max = 50)
	private BlockFloatMap pointsMap = new BlockFloatMap();

	public MiningSettings() {
		factorMap.setDefault(0);
		pointsMap.setDefault(0);
		
		factorMap.setBlock(Blocks.field_150365_q, 1);
		pointsMap.setBlock(Blocks.field_150365_q, 0);

		factorMap.setBlock(Blocks.field_150366_p, 1);
		pointsMap.setBlock(Blocks.field_150366_p, 1);

		factorMap.setBlock(Blocks.field_150450_ax, 1);
		pointsMap.setBlock(Blocks.field_150450_ax, 1);

		factorMap.setBlock(Blocks.field_150352_o, 3);
		pointsMap.setBlock(Blocks.field_150352_o, 2);

		factorMap.setBlock(Blocks.field_150369_x, 2);
		pointsMap.setBlock(Blocks.field_150369_x, 2);

		factorMap.setBlock(Blocks.field_150482_ag, 5);
		pointsMap.setBlock(Blocks.field_150482_ag, 5);

		factorMap.setBlock(Blocks.field_150412_bA, 5);
		pointsMap.setBlock(Blocks.field_150412_bA, 5);

		factorMap.setBlock(Blocks.field_150449_bY, 1);
		pointsMap.setBlock(Blocks.field_150449_bY, 0);

		factorMap.setBlock(Blocks.field_150426_aN, 2);
		pointsMap.setBlock(Blocks.field_150426_aN, 0);
	}

	public float getDoubleBonus() {
		return doubleBonus;
	}

	public float getRandomness() {
		return randomness;
	}

	public BlockFloatMap getFactorMap() {
		return factorMap;
	}

	public BlockFloatMap getPointsMap() {
		return pointsMap;
	}
}

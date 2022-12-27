import numpy as np
from gdtk.geom.path import Arc, Line
from gdtk.geom.vector3 import Vector3
from gdtk.geom.surface import CoonsPatch
from hypervehicle.components.component import Component
from hypervehicle.components.constants import FUSELAGE_COMPONENT
from hypervehicle.geometry import (
    ConePatch,
    RotatedPatch,
    OffsetPatchFunction,
    RevolvedPatch,
    SweptPatch,
)


class Fuselage(Component):
    componenttype = FUSELAGE_COMPONENT

    def __init__(self, params: dict, verbosity: int = 1) -> None:
        super().__init__(params, verbosity)

    def generate_patches(self):
        offset = self.params["OFFSET"] if "OFFSET" in self.params else None
        revolve_line = self.params["revolve_line"]

        if revolve_line is not None:
            # Create fuselage patches by revolving line
            for i in range(4):
                self.patches[f"revolved_fuse_{i}"] = RevolvedPatch(
                    revolve_line, i * np.pi / 2, (i + 1) * np.pi / 2
                )

        elif self.params["cross_sections"] is not None:
            # Create swept fuselage from cross sections
            p = SweptPatch(
                self.params["cross_sections"],
                sweep_axis=self.params["sweep_axis"],
            )

            self.patches["swept_fuse"] = p
            self.patches["swept_fuse_end_0"] = self.params["cross_sections"][0]
            self.patches["swept_fuse_end_1"] = self.params["cross_sections"][-1]

        else:
            # Legacy fuselage construction
            Xn = self.params["Xn"]
            X1 = self.params["X1"]
            X2 = self.params["X2"]
            X3 = self.params["X3"]
            X4 = self.params["X4"] if "X4" in self.params else None
            R1 = self.params["R1"]
            R2 = self.params["R2"]
            R3 = self.params["R3"]

            if self.verbosity > 0:
                print("Creating fuselage patches...")

            if self.verbosity > 1:
                print(
                    "  Fuselage nose - {}".format(self.params["FUSELAGE_NOSE_OPTION"])
                )
            if self.params["FUSELAGE_NOSE_OPTION"] == "sharp-cone":
                # create cylinder-0
                self.patches["cone_0_n"] = ConePatch(
                    x0=Xn,
                    x1=X1,
                    r0=0.0,
                    r1=R1,
                    angle0=np.deg2rad(45.0),
                    angle1=np.deg2rad(135.0),
                )
                self.patches["cone_0_e"] = RotatedPatch(
                    underlying_surf=self.patches["cone_0_n"],
                    angle=np.deg2rad(90.0),
                )
                self.patches["cone_0_s"] = RotatedPatch(
                    underlying_surf=self.patches["cone_0_n"],
                    angle=np.deg2rad(180.0),
                )
                self.patches["cone_0_w"] = RotatedPatch(
                    underlying_surf=self.patches["cone_0_n"],
                    angle=np.deg2rad(270.0),
                )
            else:
                raise Exception(
                    "Value set for FUSELAGE_NOSE_OPTION = '{}' is not supported".format(
                        self.params["FUSELAGE_NOSE_OPTION"]
                    )
                )

            # create cylinder-1
            self.patches["cone_1_n"] = ConePatch(
                x0=X1,
                x1=X2,
                r0=R1,
                r1=R2,
                angle0=np.deg2rad(45.0),
                angle1=np.deg2rad(135.0),
            )
            self.patches["cone_1_e"] = RotatedPatch(
                underlying_surf=self.patches["cone_1_n"], angle=np.deg2rad(90.0)
            )
            self.patches["cone_1_s"] = RotatedPatch(
                underlying_surf=self.patches["cone_1_n"], angle=np.deg2rad(180.0)
            )
            self.patches["cone_1_w"] = RotatedPatch(
                underlying_surf=self.patches["cone_1_n"], angle=np.deg2rad(270.0)
            )

            # create cylinder-2
            self.patches["cone_2_n"] = ConePatch(
                x0=X2,
                x1=X3,
                r0=R2,
                r1=R3,
                angle0=np.deg2rad(45.0),
                angle1=np.deg2rad(135.0),
            )
            self.patches["cone_2_e"] = RotatedPatch(
                underlying_surf=self.patches["cone_2_n"], angle=np.deg2rad(90.0)
            )
            self.patches["cone_2_s"] = RotatedPatch(
                underlying_surf=self.patches["cone_2_n"], angle=np.deg2rad(180.0)
            )
            self.patches["cone_2_w"] = RotatedPatch(
                underlying_surf=self.patches["cone_2_n"], angle=np.deg2rad(270.0)
            )

            if self.verbosity > 1:
                print(f"  Fuselage tail - {self.params['FUSELAGE_TAIL_OPTION']}")

            # create tail
            if self.params["FUSELAGE_TAIL_OPTION"].lower() == "flat":
                # create the tail (blunt)
                t_ratio = 0.3
                cos_angle = np.cos(np.deg2rad(45.0))
                p00 = Vector3(
                    x=X3,
                    y=-t_ratio * R3 * cos_angle,
                    z=t_ratio * R3 * cos_angle,
                )
                p10 = Vector3(
                    x=X3, y=t_ratio * R3 * cos_angle, z=t_ratio * R3 * cos_angle
                )
                p01 = Vector3(
                    x=X3,
                    y=-t_ratio * R3 * cos_angle,
                    z=-t_ratio * R3 * cos_angle,
                )
                p11 = Vector3(
                    x=X3,
                    y=t_ratio * R3 * cos_angle,
                    z=-t_ratio * R3 * cos_angle,
                )
                tail_centre_patch = CoonsPatch(p00=p00, p10=p10, p01=p01, p11=p11)
                self.patches["tail_centre_patch"] = tail_centre_patch

                a = Vector3(x=X3, y=-R3 * cos_angle, z=-R3 * cos_angle)
                b = Vector3(x=X3, y=R3 * cos_angle, z=-R3 * cos_angle)
                c = Vector3(x=X3, y=0.0, z=0.0)
                tail_edge_patch_n = CoonsPatch(
                    north=Arc(a=a, b=b, c=c),
                    south=Line(p0=p01, p1=p11),
                    west=Line(p0=p01, p1=a),
                    east=Line(p0=p11, p1=b),
                )
                self.patches["tail_edge_patch_n"] = tail_edge_patch_n
                self.patches["tail_edge_patch_e"] = RotatedPatch(
                    underlying_surf=tail_edge_patch_n, angle=np.deg2rad(90.0)
                )
                self.patches["tail_edge_patch_s"] = RotatedPatch(
                    underlying_surf=tail_edge_patch_n, angle=np.deg2rad(180.0)
                )
                self.patches["tail_edge_patch_w"] = RotatedPatch(
                    underlying_surf=tail_edge_patch_n, angle=np.deg2rad(270.0)
                )

            elif self.params["FUSELAGE_TAIL_OPTION"].lower() == "sharp-cone":
                # create cylinder-0
                self.patches["cone_3_n"] = ConePatch(
                    x0=X3,
                    x1=X4,
                    r0=R2,
                    r1=0.0,
                    angle0=np.deg2rad(45.0),
                    angle1=np.deg2rad(135.0),
                )
                self.patches["cone_3_e"] = RotatedPatch(
                    underlying_surf=self.patches["cone_3_n"],
                    angle=np.deg2rad(90.0),
                )
                self.patches["cone_3_s"] = RotatedPatch(
                    underlying_surf=self.patches["cone_3_n"],
                    angle=np.deg2rad(180.0),
                )
                self.patches["cone_3_w"] = RotatedPatch(
                    underlying_surf=self.patches["cone_3_n"],
                    angle=np.deg2rad(270.0),
                )

            else:
                raise Exception(
                    "Value set for FUSELAGE_TAIL_OPTION = '{}' is not supported".format(
                        self.params["FUSELAGE_TAIL_OPTION"]
                    )
                )

        if offset is not None:
            for patch_name, patch in self.patches.items():
                # Overwrite patches with offset patches
                self.patches[patch_name] = OffsetPatchFunction(patch, offset)

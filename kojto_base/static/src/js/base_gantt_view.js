/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { BaseGanttArchParser } from "./base_gantt_arch_parser";
import { BaseGanttController } from "./base_gantt_controller";
import { BaseGanttRenderer } from "./base_gantt_renderer";
import { BaseGanttModel } from "./base_gantt_model";

export const Basegantt = {
    type: "gantt",
    display_name: _t("Gantt View"),
    icon: "fa fa-tasks",
    multiRecord: true,
    ArchParser: BaseGanttArchParser,
    Controller: BaseGanttController,
    Model: BaseGanttModel,
    Renderer: BaseGanttRenderer,
    buttonTemplate: "web_base_project_gantt_view.Buttons",
    props: (genericProps, view, config) => {
        let modelParams = genericProps.state;
        if (!modelParams) {
            const { arch,  resModel, fields, context} = genericProps;
            const parser = new view.ArchParser();
            const archInfo = parser.parse(arch);
            const views = config.views || [];

            modelParams = {
                context: context,
                fields: fields,
                dateStartField: archInfo.start_date || false,
                dateStopField: archInfo.stop_date || false,
                parentField: archInfo.parent_id || false,
                userIdsField: archInfo.user_ids || false,
                colorField: archInfo.color,
                taskProgress: archInfo.task_progress|| false,
                timeFrame: archInfo.timeFrame|| 'Week',
                hasFormView: views.some((view) => view[1] === "form"),
                resModel: resModel,
                defaultOrder: 'id',
            };
        }

        return {
            ...genericProps,
            Model: view.Model,
            modelParams,
            Renderer: view.Renderer,
            buttonTemplate: view.buttonTemplate,
        };
    }
};

registry.category('views').add('gantt', Basegantt);
